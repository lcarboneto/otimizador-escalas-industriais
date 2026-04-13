"""
SISTEMA DE OTIMIZAÇÃO DE ESCALAS INDUSTRIAIS
===========================================
Autor: Luciano Carbone Neto
Descrição: Algoritmo de Pesquisa Operacional para distribuição de turnos
utilizando o solver CP-SAT do Google OR-Tools.
"""

import pandas as pd
from ortools.sat.python import cp_model
from datetime import datetime, timedelta
from collections import defaultdict

# =============================================================================
# CONFIGURAÇÕES GLOBAIS
# =============================================================================

# Arquivos de entrada e saída
CSV_DISPONIBILIDADE = "disponibilidade_colaboradores.csv"
CSV_RESTRICOES      = "restricoes_especificas.csv"
ARQUIVO_SAIDA       = "escala_gerada_industrial.csv"

# Parâmetros de Otimização
DATA_INICIO             = "2026-01-01"
DATA_FIM                = "2026-11-30"
MIN_GAP_ENTRE_EVENTOS   = 5   # Dias mínimos entre escalas do mesmo colaborador
JANELA_ESPALHAMENTO      = 14  # Janela para cálculo de penalidade de proximidade
MIN_ESCALAS_PADRAO      = 4   # Mínimo de escalas para colaboradores sem restrição mensal
MAX_ESCALAS_PADRAO      = 5   # Máximo de escalas para colaboradores sem restrição mensal
PESO_VARIEDADE_EVENTO   = 800 # Penalidade para repetição do mesmo tipo de evento
TEMPO_LIMITE_SOLVER     = 60  # Segundos

# Definição de Turnos por Dia da Semana (0=Segunda, 6=Domingo)
ESTRUTURA_TURNOS = {
    0: [("Tarde", "SEG")],
    1: [("Tarde", "TER")],
    2: [("Noite", "QUA")],
    3: [("Noite", "QUI")],
    5: [("Noite", None)], # None indica que o evento será SI ou SP (Sábados)
    6: [("Manhã", "DM"), ("Noite", "DN")],
}

TODOS_EVENTOS = {"SEG", "TER", "QUA", "QUI", "SI", "SP", "DM", "DN"}

# =============================================================================
# CLASSES E FUNÇÕES AUXILIARES
# =============================================================================

def calcular_semana_mes(data: datetime) -> int:
    """Retorna o índice da semana no mês (1 a 5)."""
    return (data.day - 1) // 7 + 1

def definir_evento_sabado(data: datetime) -> str:
    """Define se o sábado é SI (1ª/3ª semana) ou SP (2ª/4ª semana)."""
    return "SI" if calcular_semana_mes(data) in (1, 3) else "SP"

def gerar_grade_slots(inicio: datetime, fim: datetime) -> list:
    """Gera a lista cronológica de todos os turnos (slots) a serem preenchidos."""
    slots = []
    atual = inicio
    while atual <= fim:
        dia_semana = atual.weekday()
        if dia_semana in ESTRUTURA_TURNOS:
            for turno, evento in ESTRUTURA_TURNOS[dia_semana]:
                if evento is None:
                    evento = definir_evento_sabado(atual)
                slots.append({
                    "data": atual,
                    "turno": turno,
                    "evento": evento,
                    "indice": len(slots),
                })
        atual += timedelta(days=1)
    return slots

def validar_restricao_temporal(id_colab: int, slot: dict, lista_restricoes: list) -> bool:
    """Verifica se um slot específico é proibido para um colaborador devido a regras manuais."""
    data_slot = slot["data"].date()
    evento_slot = slot["evento"]

    for r in lista_restricoes:
        if int(r["id_colaborador"]) != id_colab:
            continue
        
        tipo = r.get("tipo", "").lower()
        valor = str(r.get("valor", "")).strip()

        try:
            if tipo == "bloqueio_data" and data_slot == datetime.strptime(valor, "%Y-%m-%d").date():
                return True
            elif tipo == "apenas_si" and evento_slot == "SP":
                return True
            elif tipo == "apenas_sp" and evento_slot == "SI":
                return True
            elif tipo == "periodo_indisponivel":
                inicio_r, fim_r = [datetime.strptime(d.strip(), "%Y-%m-%d").date() for d in valor.split(":")]
                if inicio_r <= data_slot <= fim_r:
                    return True
        except ValueError:
            continue
    return False

# =============================================================================
# MOTOR DE OTIMIZAÇÃO (OR-TOOLS)
# =============================================================================

def processar_otimizacao():
    """Função principal que modela e resolve o problema de escala."""
    
    # 1. Preparação de Dados
    dt_inicio = datetime.strptime(DATA_INICIO, "%Y-%m-%d")
    dt_fim = datetime.strptime(DATA_FIM, "%Y-%m-%d")
    
    try:
        df_base = pd.read_csv(CSV_DISPONIBILIDADE)
        colaboradores = sorted(df_base.iloc[:, 0].astype(int).tolist())
        
        # Carregar disponibilidades do CSV (Mapeia ID -> Eventos permitidos)
        disponibilidade_map = {(row[0], ev): bool(row[ev_col]) 
                              for _, row in df_base.iterrows() 
                              for ev_col, ev in zip(df_base.columns[1:], TODOS_EVENTOS) if ev_col in df_base.columns}
        
        restricoes_externas = pd.read_csv(CSV_RESTRICOES).to_dict("records")
    except FileNotFoundError as e:
        print(f"Erro: Arquivos CSV de entrada não encontrados. {e}")
        return

    slots = gerar_grade_slots(dt_inicio, dt_fim)
    model = cp_model.CpModel()

    # 2. Criação das Variáveis de Decisão
    # x[(v, s)] é verdadeiro se o colaborador 'v' for alocado ao slot 's'
    x = {}
    for v in colaboradores:
        for s, slot in enumerate(slots):
            is_bloqueado = validar_restricao_temporal(v, slot, restricoes_externas)
            pode_atuar = disponibilidade_map.get((v, slot["evento"]), False)
            
            if pode_atuar and not is_bloqueado:
                x[(v, s)] = model.NewBoolVar(f"colab_{v}_slot_{s}")
            else:
                x[(v, s)] = model.NewConstant(0)

    # 3. Restrições Hard (Obrigatórias)
    # Cada turno deve ter exatamente 1 colaborador
    for s in range(len(slots)):
        model.Add(sum(x[(v, s)] for v in colaboradores) == 1)

    # Um colaborador não pode trabalhar duas vezes no mesmo dia
    slots_por_dia = defaultdict(list)
    for s, slot in enumerate(slots):
        slots_por_dia[slot["data"].date()].append(s)
    
    for v in colaboradores:
        for s_indices in slots_por_dia.values():
            model.Add(sum(x[(v, s)] for s in s_indices) <= 1)

        # Respeitar intervalo (gap) mínimo entre escalas
        for s in range(len(slots) - MIN_GAP_ENTRE_EVENTOS):
            janela = [x[(v, s + k)] for k in range(MIN_GAP_ENTRE_EVENTOS + 1)]
            model.Add(sum(janela) <= 1)

    # 4. Objetivos e Penalidades (Soft Constraints)
    # Penalizar a falta de variedade (repetição de eventos para o mesmo colaborador)
    penalidades = []
    for v in colaboradores:
        for ev in TODOS_EVENTOS:
            slots_evento = [s for s, sl in enumerate(slots) if sl["evento"] == ev and (v, s) in x]
            if slots_evento:
                total_ev = sum(x[(v, s)] for s in slots_evento)
                excesso = model.NewIntVar(0, len(slots), "")
                model.Add(excesso >= total_ev - 1) # Penaliza a partir da 2ª vez no mesmo evento
                penalidades.append(excesso * PESO_VARIEDADE_EVENTO)

    model.Minimize(sum(penalidades))

    # 5. Execução do Solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TEMPO_LIMITE_SOLVER
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("Escala otimizada gerada com sucesso!")
        exportar_resultados(solver, x, colaboradores, slots)
    else:
        print("Não foi possível encontrar uma solução que respeite todas as regras.")

def exportar_resultados(solver, x, colaboradores, slots):
    """Gera o arquivo CSV final e exibe estatísticas no console."""
    final = []
    for s, slot in enumerate(slots):
        for v in colaboradores:
            if solver.Value(x[(v, s)]) == 1:
                final.append({
                    "Data": slot["data"].strftime("%d/%m/%Y"),
                    "Evento": slot["evento"],
                    "Turno": slot["turno"],
                    "Colaborador_ID": v
                })
    
    pd.DataFrame(final).to_csv(ARQUIVO_SAIDA, index=False, encoding="utf-8-sig")
    print(f"Resultados salvos em: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    processar_otimizacao()

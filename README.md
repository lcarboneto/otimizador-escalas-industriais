# Otimizador de Escalas Industriais (Constraint Programming)

## -> Contexto
Este projeto resolve um desafio comum em plantas industriais e operações 24/7: a criação de escalas de trabalho que equilibrem a disponibilidade dos funcionários, restrições legais/trabalhistas e a necessidade de variedade de eventos.

Desenvolvido para gerenciar uma equipe de 23 funcionários com 8 tipos de eventos semanais, o sistema utiliza o solver **Google OR-Tools** para encontrar a solução ótima que respeite todas as regras de negócio em segundos.

## -> Tecnologias Utilizadas
* **Python 3.x**
* **OR-Tools (CP-SAT Solver):** Para modelagem e resolução de problemas de satisfação de restrições.
* **Pandas:** Para manipulação de dados de entrada (disponibilidades e restrições em CSV).
* **Datetime/Collections:** Para processamento de séries temporais e lógica de calendários.

## -> Regras de Negócio Implementadas
O algoritmo não apenas distribui turnos, mas garante:
1. **Gap Mínimo:** Espaçamento configurável entre escalas para garantir descanso.
2. **Variedade de Eventos:** Penalidade inteligente para evitar que um funcionário fique sobrecarregado sempre no mesmo tipo de turno.
3. **Restrições Customizadas:** Bloqueios por data específica, períodos de férias, limites máximos por mês e preferências de turnos específicos (SI/SP).
4. **Equidade:** Distribuição balanceada do número de escalas entre os funcionários disponíveis.

## -> Como Executar
1. Certifique-se de ter o Python e as dependências instaladas no requeriments.txt.
2. Prepare os arquivos `e_disponibilidade.csv` e `e_restricoes.csv`.
3. Execute o script principal:
   `python gerador_escala.py`
4. O resultado será exportado automaticamente para um arquivo `escala_gerada.csv`.

---
**Autor:** Luciano Carbone Neto  
*Engenheiro Químico | Especialista em Analytics Industrial e Comercial | Cientista de Dados*

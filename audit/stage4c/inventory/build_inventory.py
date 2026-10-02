"""
Stage 4C.1 — inventário e classificação das guardas históricas.

    python audit/stage4c/inventory/build_inventory.py            # grava guard_inventory.json + tabela .md
    python audit/stage4c/inventory/build_inventory.py --check    # só confere (nada é gravado)

Fonte única da classificação H/E/R/S/W/C (contrato 4C §2). As linhas (`arquivo:linha`) são as da
definição do teste na árvore em que o inventário é gerado (commit 4c.1, ANTES de qualquer conversão),
achadas pelo nome — nunca digitadas à mão. Cada entrada traz a referência atual (o que o teste lê hoje),
a referência nova (o que vai ler depois da Fase 2) e a justificativa.

Critério de inclusão: todo teste que (a) cita hash de commit, (b) compara HEAD/árvore com commit,
(c) compara execução viva com evidência versionada ou expectativas JSON, (d) congela cardinalidades,
IDs, vínculos ou SHAs e falha no ensaio R1 (energy v9 + MaxHT v13) ou (e) verifica que a árvore não mudou.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

CLASSES = {
    "H": "fechamento histórico — intervalo fixo baseline..fechamento; nunca lê HEAD",
    "E": "imutabilidade de evidência histórica — arquivo do HEAD x commit de fechamento",
    "R": "regressão viva — referência do registro `current`; harness recebe só parâmetro de diretório",
    "S": "invariante semântico — IDs não renumerados, aposentados no `retired`, sem reuso, faixas",
    "W": "árvore intacta pela execução — status antes/depois",
    "C": "contrato de conteúdo atual — NÃO alterado na 4C; pré-lista da 5A",
}

# Commits de fechamento (reconfirmados por `git log` na 4C.1).
A126 = "a126e02"   # 2.6 (auditoria)
ECEF = "eceffd4"   # 2.6B (auditoria)
S26C = "7877551"   # 2.6C (auditoria; REFERENCE da 3.4B)
S32 = "a733487"    # 3.2 (auditoria)
S33A = "eee88d6"   # 3.3A (auditoria, gate PASS)
S34B = "4d54804"   # 3.4B (fechamento)
S34C = "043fe9c"   # 3.4C (fechamento; BASELINE da 3.4D)
S34D = "8095011"   # 3.4D (fechamento)
S34E = "547b920"   # 3.4E / Stage 3 (PRE_MIGRATION da D-TAX-01)
DTAX1 = "d8b5d55"  # D-TAX-01
DTAX2 = "d2847ab"  # D-TAX-02 (baseline da 4A)
S4A = "0a924e6"    # 4A (fechamento; baseline da 4B)
S4B = "f573c1b"    # 4B (fechamento; = B0.commit_comportamento)

E = []


def add(test, cls, now, new, why, r1=None):
    E.append({"test": test, "class": cls, "reference_now": now, "reference_new": new, "justification": why,
              "r1_failed": r1})


# ------------------------------------------------------------------ Stage 2.x
add("tests/test_stage2_6b_interblock_closure.py::test_no_historical_id_was_renumbered", "S",
    f"`git show {A126}:manifest` x seed do HEAD; exige removed == added == ∅ (exceto production)",
    f"S: chaves comuns com o mesmo ID; removidas => ID no `retired` do ledger; novas => ID nunca emitido; "
    f"o literal de production (lth_meta) vira H no intervalo {A126}..{ECEF}",
    "congela o conjunto de entidades desde a 2.6; a 5A aposenta VAR13001–13006 e cria VAR18053/VAR13117–13123 "
    "legitimamente. O invariante real (sem renumeração, sem reuso) continua ao vivo")
add("tests/test_stage2_6c_interblock_final.py::test_12_ids_are_stable_against_baselines", "S",
    f"`git show {A126}|{ECEF}:manifest` x HEAD; para {ECEF} exige before == after",
    f"S ao vivo (mesmas regras); o `before == after` de {ECEF} vira H no intervalo {ECEF}..{S26C}",
    "idem; o congelamento total era a afirmação do fechamento 2.6C")
add("tests/test_stage2_6c_interblock_final.py::test_13_retired_ids_are_recorded_and_never_reused", "S",
    "ledger do HEAD", "sem alteração", "já é o invariante S (retired listado, sem reuso)")
add("tests/test_stage2_6b_interblock_closure.py::test_ledger_retires_ids_and_never_reuses_them", "S",
    "ledger do HEAD + build", "sem alteração", "invariante S; passa no ensaio R1")
add("tests/test_stage2_6b_interblock_closure.py::test_17_max_ht_is_the_canonical_block_name", "C",
    "literal `descritivo_das_variáveis_MaxHT_v10.xlsx`", "sem alteração (pré-lista 5A)",
    "nome do workbook vigente é conteúdo atual", True)
add("tests/test_stage2_6b_interblock_closure.py::test_18_all_real_links_of_the_five_workbooks", "C",
    "conjunto EXPECTED de vínculos (32 linhas fonte)", "sem alteração (pré-lista 5A)",
    "vínculos declarados nos workbooks vigentes", True)
add("tests/test_stage2_6c_interblock_final.py::test_17_independent_analysis_matches_the_builder", "C",
    "análise 2.6C ao vivo + literal {SOURCE_BLOCK_NOT_LOADED: 16, VALID: 13}", "sem alteração (pré-lista 5A)",
    "contagens de vínculos do conteúdo vigente", True)
add("tests/test_stage2_6c_interblock_final.py::test_14_repeated_builds_are_byte_identical_and_order_independent", "S",
    "build isolado x seeds do HEAD", "sem alteração", "determinismo do gerador; independe do conteúdo")
add("tests/test_stage2_6_interblock_contract.py::test_15_every_real_fonte_is_classified", "C",
    "conjunto literal de vínculos reais", "sem alteração (pré-lista 5A)", "conteúdo dos workbooks", True)
add("tests/test_stage2_4_workbook_contract.py::test_t24_02_each_block_builder_consumes_its_approved_workbook", "C",
    "linhas por workbook (56/120…)", "sem alteração (pré-lista 5A)", "cardinalidade do workbook vigente", True)
add("tests/test_stage2_4_workbook_contract.py::test_t24_02_total_rows_and_equations_match_stage_2_3", "C",
    "total 572 linhas", "sem alteração (pré-lista 5A)", "cardinalidade do workbook vigente", True)
add("tests/test_stage2_4_workbook_contract.py::test_t24_06_max_ht_v9_ignores_trailing_empty_rows", "C",
    "120 linhas do MaxHT", "sem alteração (pré-lista 5A)", "cardinalidade do workbook vigente", True)
add("tests/test_aggregation_dimensions.py::test_sum_factors_follow_the_approved_workbook_units", "C",
    "unidades por fator de integração", "sem alteração (pré-lista 5A)", "unidades do workbook vigente", True)

# ------------------------------------------------------------------ energy / max_ht (conteúdo)
for name in ("test_entity_counts_match_the_workbook", "test_equation_and_aggregation_counts",
             "test_all_ids_are_inside_the_energy_range_and_unique", "test_energy_ids_do_not_collide_with_other_blocks",
             "test_variable_frequency_distribution", "test_variable_type_distribution", "test_scope_distribution",
             "test_variable_instances_are_materialized_by_the_real_resolver",
             "test_explicit_scoped_references_are_extracted",
             "test_energia_bayer_and_energia_media_frct_bind_by_id_not_name"):
    add(f"tests/test_energy_seed_contract.py::{name}", "C", "literais do seed energy v6", "sem alteração (pré-lista 5A)",
        "contrato do conteúdo energy vigente", True)
for name in ("test_the_23_daily_equations_all_execute", "test_per_line_results", "test_plant_group_results",
             "test_subgroup_specific_evaporation", "test_both_branches_of_the_conditional_are_exercised",
             "test_energia_bayer_equals_digestion_plus_evaporation", "test_no_calculated_variable_was_seeded_by_hand",
             "test_perturbing_one_line_propagates_to_the_plant",
             "test_perturbing_an_unrelated_line_does_not_change_a_subgroup",
             "test_cross_block_inputs_are_declared_as_inputs_with_a_source",
             "test_daily_to_monthly_chain_feeds_eq18020", "test_eq18020_cannot_be_satisfied_by_daily_values_alone"):
    add(f"tests/test_energy_runtime_contract.py::{name}", "C", "fixture de entradas do energy v6",
        "sem alteração (pré-lista 5A)", "execução do conteúdo energy vigente (entrada nova VAR18053 ausente do fixture)",
        True)
for name in ("test_entity_counts", "test_all_math_equations_parse_successfully", "test_full_seed_root_loads_without_errors"):
    add(f"tests/test_max_ht_runtime_contract.py::{name}", "C", "literais do seed max_ht v10",
        "sem alteração (pré-lista 5A)", "contrato do conteúdo max_ht vigente", True)

# ------------------------------------------------------------------ Stage 3.x
add("tests/test_stage3_3a_result_contract.py::test_23_25_planning_code_is_unchanged_since_stage_3_2", "H",
    f"`git show {S32}:interblock_orchestrator.py` x arquivo do HEAD",
    f"funções do planner em {S32} x em {S33A} (fechamento 3.3A)",
    "a afirmação é da 3.3A (o contrato de resultado não mexeu no planner); regressões de plano no HEAD são "
    "pegas pelos testes R (plan_order nos fingerprints)")
add("tests/test_stage3_4b_differential.py::test_live_differential_reference_vs_head_matches_exactly", "H",
    f"harness ao vivo {S26C} x HEAD sobre data/seed do HEAD",
    f"mesmo harness, sem alteração, executado num clone temporário no fechamento {S34B} ({S26C}..{S34B})",
    "o runtime de referência (7877551) não carrega dados futuros (unidades novas); a afirmação diferencial é "
    "histórica da 3.4B. Regressão do app no HEAD fica com os testes R (3.4C/4A/4B)", True)
add("tests/test_stage3_4b_differential.py::test_committed_evidence_reproduces_the_full_matrix", "H",
    "evidência versionada x universo dos seeds do HEAD",
    f"evidência versionada x universo dos seeds em {S34B} (calculado no clone)",
    "a evidência descreve o universo do seu fechamento", True)
add("tests/test_stage3_4b_differential.py::test_committed_summary_is_the_differential_oracle", "E",
    "summary versionado", "sem alteração (+ sha256 no B0 e diff x fechamento)", "evidência histórica")
add("tests/test_stage3_4c_integrated.py::test_live_integrated_regression_passes", "R",
    "harness ao vivo + literais 446/25/421/427/218/197/12",
    "harness com `--baseline-dir` do current; literais = universo da referência do registro (B0 = mesmos literais, "
    "provado em test_stage4c_baseline_registry)", "regressão viva do HEAD", True)
add("tests/test_stage3_4c_integrated.py::test_live_run_reproduces_committed_evidence_and_is_deterministic", "R",
    "`audit/stage3_4/integrated/evidence/integrated_summary.json`", "arquivo do conjunto stage3_4c_integrated do current",
    "regressão viva x referência aprovada", True)
add("tests/test_stage3_4c_integrated.py::test_committed_targets_nodes_transfers_and_coverage_are_complete", "R",
    "CSVs versionados x plano vivo + literais 421/427/12/60",
    "CSVs do current x plano vivo; literais da referência", "compara plano vivo com evidência", True)
add("tests/test_stage3_4c_integrated.py::test_committed_summary_contract", "E",
    "summary versionado", "sem alteração", "conteúdo da evidência histórica")
add("tests/test_stage3_4c_integrated.py::test_area_41_is_outside_the_integrated_universe", "C",
    "literal 25 alvos do area_41", "sem alteração (pré-lista 5A)", "cardinalidade do conteúdo vigente")
add("tests/test_stage3_4d_mutation.py::test_live_evidence_mutations_are_all_detected", "H",
    "harness de mutação ao vivo no HEAD (alvos VAR13001–13003, BASELINE 043fe9c)",
    f"mesmo harness, sem alteração, num clone temporário em {S34D} (fechamento 3.4D)",
    "a matriz de mutações nomeia IDs reais que a 5A aposenta (VAR13001–13003); a afirmação "
    "'auditores 3.4B/3.4C detectam 100%' é do fechamento", True)
add("tests/test_stage3_4d_mutation.py::test_live_run_reproduces_committed_mutation_results", "H",
    "resultado vivo x mutation_results.csv", f"resultado no clone {S34D} x mutation_results.csv (E)",
    "idem", True)
add("tests/test_stage3_4d_mutation.py::test_live_code_mutant_is_killed_in_a_temporary_copy", "H",
    "mutante CM-13 numa cópia do HEAD + status antes/depois",
    f"mutante CM-13 numa cópia de {S34D}; status antes/depois do repositório (W) mantido",
    "os detectores 'TESTS' rodam a suíte da cópia; no HEAD futuro a suíte tem falhas C alheias ao mutante", True)
add("tests/test_stage3_4d_mutation.py::test_no_production_artifact_changed_since_baseline", "H",
    f"`classify_git({S34C})` x árvore de trabalho", f"`classify_git({S34C}, {S34D})`",
    "afirmação do fechamento 3.4D", True)
for name in ("test_committed_mutation_matrix_is_formal_and_complete", "test_committed_code_mutants_have_no_survivors",
             "test_blackbox_audit_passes_without_importing_app", "test_blackbox_audit_rejects_corrupted_evidence",
             "test_baseline_gaps_are_recorded_and_closed"):
    add(f"tests/test_stage3_4d_mutation.py::{name}", "E", "artefatos versionados da 3.4B/3.4C/3.4D",
        "sem alteração (+ sha256 no B0 e diff x fechamento)", "só lê evidência histórica")

# ------------------------------------------------------------------ D-TAX-01 / D-TAX-02
for name in ("test_tax_06_no_id_changed_by_the_rename", "test_tax_07_no_formula_changed",
             "test_tax_08_no_interblock_link_changed_semantically", "test_tax_09_the_16_pending_load_links_are_identical",
             "test_cardinalities_results_and_graph_unchanged"):
    add(f"tests/test_taxonomy_migration_d_tax_01.py::{name}", "H",
        f"snapshot da árvore de trabalho x before_snapshot.json ({S34E})",
        f"snapshot calculado num clone temporário em {DTAX1} x before_snapshot.json",
        "a migração D-TAX-01 é exclusivamente nomenclatural NO SEU INTERVALO; a árvore futura muda seeds legitimamente",
        True)
add("tests/test_taxonomy_migration_d_tax_01.py::test_tax_10_the_authorized_change_is_detected_as_taxonomic_not_functional",
    "H", f"`classify_git({S34E})` e `protected_status(ref, None)` x árvore de trabalho",
    f"`classify_git({S34E}, {DTAX1})` e `protected_status(ref, {DTAX1})`", "idem", True)
add("tests/test_taxonomy_migration_d_tax_01.py::test_guard_rejects_every_non_taxonomic_change", "H",
    f"`changes_between({S34E})` (árvore de trabalho) + arquivos do HEAD",
    f"`changes_between({S34E}, {DTAX1})` + arquivos em {DTAX1}",
    "com a árvore futura já não-taxonômica o negativo passaria por vacuidade; fixar o intervalo preserva o poder")
add("tests/test_taxonomy_migration_d_tax_01.py::test_stage3_provenance_still_rejects_masked_pending_links", "H",
    "interblock_links.json do HEAD x 043fe9c", f"interblock_links.json em {DTAX1} x 043fe9c",
    "controle positivo é o arquivo pós-migração", True)
add("tests/test_taxonomy_d_tax_02.py::test_tax_02_07_crosswalk_changes_no_id_or_range", "H",
    f"`git diff {DTAX1}` x árvore de trabalho", f"`git diff {DTAX1} {DTAX2}`; faixas ao vivo == CANONICAL (S)",
    "afirmação do fechamento D-TAX-02; a parte 'faixas inalteradas' segue ao vivo como S", True)
add("tests/test_taxonomy_d_tax_02.py::test_tax_02_05_historical_names_are_not_canonical_anywhere_operational", "S",
    "`git grep` no HEAD", "sem alteração", "invariante vivo; independe de conteúdo")

# ------------------------------------------------------------------ Stage 4A
add("tests/test_stage4a_closure.py::test_independent_reconciliation_passes_without_app", "H",
    "reconcile_4a.py no HEAD (recontagem viva + `git diff d2847ab`)",
    f"reconcile_4a.py, sem alteração, num clone temporário em {S4A}; o JSON versionado segue E",
    "reconciliação de fechamento", True)
add("tests/test_stage4a_closure.py::test_production_surface_and_stage_3_closure_untouched", "H",
    f"`git diff {DTAX2}` x HEAD", f"`git diff {DTAX2} {S4A}` (F4B-06)",
    "a guarda fecha a 4A; lida contra o HEAD falha a cada stage posterior (F4B-06)", True)
add("tests/test_stage4a_closure.py::test_pending_items_dated_addition_keeps_f01_f02_open_and_f03_partial", "S",
    f"`git show {DTAX2}:PLATFORM_PENDING_ITEMS.md` é prefixo do HEAD", "sem alteração",
    "invariante append-only da lista mestre; continua válido com adições futuras")
add("tests/test_stage4a_closure.py::test_l8_comparison_only_area_41_changed", "E", "closure_reconciliation_4a.json",
    "sem alteração", "evidência histórica")
add("tests/test_stage4a_contract.py::test_independent_recount_matches_contract_without_importing_app", "R",
    "independent_count --check x audit/stage4a/contract_expectations.json + literais 446/458/62/896",
    "expectativas do conjunto stage4a_contract do current (`--baseline-dir`); literais = referência", "", True)
add("tests/test_stage4a_contract.py::test_nodes_are_the_union_not_the_sum", "R",
    "independent_count + literais (shared, 458)", "expectativas do current", "", True)
add("tests/test_stage4a_contract.py::test_derivation_agrees_with_independent_recount_and_frozen_expectations", "R",
    "derive_4a --no-write x contract_expectations.json", "x expectativas do current", "", True)
add("tests/test_stage4a_contract.py::test_official_plan_pending_links_and_links_sha_are_unchanged", "R",
    f"plan_evidence.csv da 3.2 + sha dos vínculos em {DTAX2} + expectativas",
    f"plan_evidence e expectativas do current (R); 'vínculos iguais no intervalo da 4A' = H ({DTAX2}..{S4A})",
    "", True)
add("tests/test_stage4a_contract.py::test_official_plan_comparator_detects_a_changed_evidence_row", "R",
    "plan_evidence.csv da 3.2", "plan_evidence do current", "negativo sobre a referência viva", True)
for name in ("test_hes_decision_tree_engine_equals_literal_workbook_in_all_50_combinations",
             "test_scopes_and_suffixes_verified_in_the_parser", "test_area_41_aggregation_rules_and_ytd_partial",
             "test_contract_document_records_decisions_findings_and_obs"):
    add(f"tests/test_stage4a_contract.py::{name}", "E", "evidência versionada da 4A", "sem alteração",
        "lê evidência histórica (a parte viva é conteúdo do area_41, inalterado)")
add("tests/test_stage4a_contract.py::test_input_protocol_keeps_every_3_4c_input_index", "C",
    "literal range(51, 62)", "sem alteração (pré-lista 5A)", "índices dependem do nº de entradas do plano vigente")
add("tests/test_stage4a_integrated.py::test_live_five_block_regression_passes_and_reproduces_committed_evidence", "R",
    "harness ao vivo x evidência 4A + contract_expectations + literais 446/458/13/421/427",
    "harness com `--baseline-dir`; literais = referência do current", "", True)
add("tests/test_stage4a_integrated.py::test_non_regression_of_the_421_previous_targets", "R",
    "3.4C integrated_summary.json/targets.csv versionados", "conjunto stage3_4c_integrated do current", "", True)
add("tests/test_stage4a_integrated.py::test_negative_corrupted_previous_key_is_detected", "R",
    "harness.non_regression em processo (3.4C versionada)", "idem, referência configurada pelo registro (conftest)",
    "", True)
add("tests/test_stage4a_integrated.py::test_negative_area_41_change_does_not_touch_the_421_check", "R",
    "idem", "idem", "", True)
add("tests/test_stage4a_integrated.py::test_stage_3_4c_evidence_is_untouched", "H",
    f"`git diff {DTAX2}` x árvore em audit/stage3_4/** e stage3_2/**",
    f"H: `git diff {DTAX2} {S4A}` nesses caminhos; E: evidência (arquivos de dados) do HEAD x {S4A}; não rastreados",
    "a 4C muda harnesses da 3.4 só para o parâmetro de diretório; a evidência continua imutável")
for name in ("test_committed_non_regression_report", "test_committed_summary_temporal_reexecution_determinism_state",
             "test_committed_csv_evidence_is_complete"):
    add(f"tests/test_stage4a_integrated.py::{name}", "E", "evidência versionada 4A (+3.4C)", "sem alteração",
        "evidência histórica")
add("tests/test_stage4a_mutation.py::test_live_evidence_mutations_are_all_detected_with_positive_controls", "R",
    "evidência 4A e expectativas versionadas", "conjuntos do current (`--baseline-dir`)", "", True)
add("tests/test_stage4a_mutation.py::test_minimum_mutant_set_is_defined_and_applies_to_unique_snippets", "C",
    "trechos do código do app no HEAD", "sem alteração (pré-lista 5A se a 5A tocar esses trechos)",
    "contrato do código atual")
add("tests/test_stage4a_mutation.py::test_mutants_never_touch_the_working_tree", "W",
    "`git status -- app data tools` vazio", "sem alteração", "árvore intacta")
for name in ("test_committed_evidence_mutation_results", "test_committed_code_mutants_all_detected_in_temporary_copies"):
    add(f"tests/test_stage4a_mutation.py::{name}", "E", "evidência versionada", "sem alteração", "")
add("tests/test_stage4a_oracle.py::test_live_oracle_agrees_with_engine_on_20_equations_and_25_hes_combinations", "C",
    "workbook A41 v9 + literais (20 equações, 25 combinações)", "sem alteração",
    "fidelidade ao workbook vigente do area_41")
add("tests/test_stage4a_oracle.py::test_committed_oracle_summary_declares_tolerance_and_limitations", "E",
    "oracle_summary.json", "sem alteração", "")

# ------------------------------------------------------------------ Stage 4B
add("tests/test_stage4b_closure.py::test_independent_reconciliation_passes_without_app", "H",
    "reconcile_4b.py no HEAD (G-01/G-02 com `git diff 0a924e6`)",
    f"reconcile_4b.py, sem alteração, num clone temporário em {S4B}; JSON versionado segue E", "", True)
add("tests/test_stage4b_closure.py::test_production_surface_and_previous_stages_untouched", "H",
    f"`git diff {S4A}` x HEAD", f"`git diff {S4A} {S4B}`; arquivos não rastreados (W) mantidos",
    "mesmo defeito do F4B-06, um fechamento adiante", True)
add("tests/test_stage4b_closure.py::test_pending_items_dated_addition_is_append_only", "S",
    f"`git show {S4A}` é prefixo do HEAD", "sem alteração", "append-only")
add("tests/test_stage4b_contract.py::test_independent_recount_matches_frozen_expectations", "R",
    "contract_expectations_4b.json + literais 324/196", "expectativas do conjunto stage4b_contract do current", "",
    True)
for name in ("test_store_growth_predicted_from_seeds_matches_engine", "test_e1_turn_of_year_windows_and_snapshot",
             "test_e2_gaps_fail_explicitly", "test_e3_no_carry_over_of_new_period_inputs",
             "test_e4_closed_periods_and_e5_calendar", "test_performance_within_contract_limit",
             "test_contract_document_records_decisions_and_findings"):
    add(f"tests/test_stage4b_contract.py::{name}", "E", "contract_audit_4b.json / contrato", "sem alteração", "")
add("tests/test_stage4b_temporal.py::test_live_t2_leap_year_passes", "R",
    "harness T2 ao vivo x evidência T2 versionada + literais 446/458/896/67",
    "harness com `--baseline-dir`; literais = referência do current", "", True)
for name in ("test_committed_runs_cover_every_date", "test_identities_and_windows_follow_the_calendar",
             "test_t1_turn_of_year_and_closed_periods", "test_prefix_invariant_against_stage_4a",
             "test_state_over_the_year_and_isolation_between_years", "test_determinism_configurations",
             "test_performance_ratio_within_limit_and_t3_leap_and_two_year_ends"):
    add(f"tests/test_stage4b_temporal.py::{name}", "E", "evidência T1/T2/T3 versionada", "sem alteração", "")
add("tests/test_stage4b_mutation.py::test_live_evidence_mutations_detected_and_controls_accepted", "R",
    "evidência T1/T2 + expectativas 4A/4B versionadas", "conjuntos do current (`--baseline-dir`)", "", True)
add("tests/test_stage4b_mutation.py::test_required_mutants_apply_to_unique_snippets", "C",
    "trechos do código do app", "sem alteração", "contrato do código atual")
add("tests/test_stage4b_mutation.py::test_working_tree_untouched", "W", "`git status` vazio", "sem alteração", "")
for name in ("test_committed_evidence_mutations_cover_every_temporal_contract", "test_committed_code_mutants_all_detected"):
    add(f"tests/test_stage4b_mutation.py::{name}", "E", "evidência versionada", "sem alteração", "")
add("tests/test_stage4b_oracle.py::test_live_oracle_t2_and_stated_run", "R",
    "contract_expectations_4b.json (intervalos) via harness", "expectativas do current", "não compara com evidência")
add("tests/test_stage4b_oracle.py::test_committed_oracle_covers_every_aggregation_on_t1_and_t2", "E",
    "oracle_temporal_summary.json", "sem alteração", "")


def locate(entry: dict) -> str:
    path, name = entry["test"].split("::")
    text = (REPO / path).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(text, 1):
        if re.match(rf"\s*def {re.escape(name)}\(", line):
            return f"{path}:{number}"
    raise SystemExit(f"teste não encontrado: {entry['test']}")


def build() -> dict:
    rows = [{**e, "location": locate(e)} for e in E]
    tests = [r["test"] for r in rows]
    assert len(tests) == len(set(tests)), "teste duplicado no inventário"
    counts = Counter(r["class"] for r in rows)
    return {"stage": "4C.1", "classes": CLASSES, "entries": rows,
            "counts": {c: counts.get(c, 0) for c in CLASSES}, "total": len(rows),
            "r1_failed_listed": sum(1 for r in rows if r["r1_failed"])}


def markdown(data: dict) -> str:
    out = ["| teste | arquivo:linha | classe | referência atual | referência nova | justificativa |",
           "|---|---|---|---|---|---|"]
    for r in data["entries"]:
        name = r["test"].split("::")[1]
        out.append(f"| `{name}` | `{r['location']}` | {r['class']} | {r['reference_now']} | "
                   f"{r['reference_new']} | {r['justification'] or '—'} |")
    return "\n".join(out) + "\n"


def main() -> int:
    data = build()
    target = HERE / "guard_inventory.json"
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        # a classificação é comparada sem as linhas (que mudam depois da conversão da Fase 2)
        strip = lambda d: [{k: v for k, v in r.items() if k != "location"} for r in d["entries"]]
        ok = target.exists() and strip(json.loads(target.read_text(encoding="utf-8"))) == strip(data)
        print(json.dumps({"total": data["total"], "counts": data["counts"], "matches_committed": ok}))
        return 0 if ok else 1
    target.write_text(text, encoding="utf-8")
    (HERE / "guard_inventory_table.md").write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"total": data["total"], "counts": data["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

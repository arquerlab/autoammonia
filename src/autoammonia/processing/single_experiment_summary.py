from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from autoammonia.processing.echem_metrics import build_lsv_metric_rows, empty_metric_rows
from autoammonia.processing.echem_traces import (
    load_lsv_traces,
    load_reaction_trace,
    load_single_trace,
    load_uvvis_spectra,
)
from autoammonia.processing.experiment_metadata import (
    load_electrodeposition_current_ma,
    load_experiment_compositions,
    load_reaction_current_ma,
    resolve_data_path_for_experiment,
)
from autoammonia.processing.fe import build_fe_interval_breakdowns, format_fe_table_rows
from autoammonia.processing.plot_style import (
    SMALL_FONT_SIZE,
    TITLE_FONT_SIZE,
    configure_summary_fonts,
    safe_plot_panel,
    safe_result,
)
from autoammonia.processing.plots.echem_panels import plot_lsv_panel, plot_ocp_overlay_panel
from autoammonia.processing.plots.protocol_panels import plot_cp_panel, plot_reaction_trace_panel
from autoammonia.processing.plots.table_panels import plot_composition_table, plot_metrics_table
from autoammonia.processing.plots.uvvis_panels import plot_absorbance_with_fe
from autoammonia.processing.processing_config import (
    get_processing_config,
    rhe_ph_for_experiment,
    setpoint_current_density_ma_cm2,
)


def plot_single_experiment_summary(
    experiment_id: int,
    out_path: Path | None = None,
    ph: float | None = None,
    ref_offset_v: float | None = None,
) -> Path:
    """Create a 2x3 summary plot for one experiment.

    Args:
        experiment_id (int): Experiment ID.
        out_path (Path | None, optional): Output PNG path. Defaults to
            `<data_path>/process/single_experiment_summary/ID<experiment_id>_single_experiment_summary.png`.
        ph (float | None, optional): Electrolyte pH for RHE conversion. If None, uses
            processing_config pH cutoffs. Defaults to None.
        ref_offset_v (float | None, optional): Ag/AgCl reference offset in volts. If None,
            uses processing_config.ref_offset_v_agagcl_3m. Defaults to None.

    Returns:
        Path: Saved plot path.
    """
    configure_summary_fonts()
    config = get_processing_config()
    ph = rhe_ph_for_experiment(experiment_id, config) if ph is None else float(ph)
    ref_offset_v = (
        config.ref_offset_v_agagcl_3m if ref_offset_v is None else float(ref_offset_v)
    )

    data_path = resolve_data_path_for_experiment(experiment_id)
    folder_uvvis = data_path / "uvvis"
    folder_electrosynthesis = data_path / "electrosynthesis"
    folder_electrodeposition = data_path / "electrodeposition"
    folder_electrodissolution = data_path / "electrodissolution"

    if out_path is None:
        out_path = (
            data_path
            / "process"
            / "single_experiment_summary"
            / f"ID{experiment_id}_single_experiment_summary.png"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    catalyst_text, electrolyte_text = load_experiment_compositions(experiment_id)
    reaction_current_ma = load_reaction_current_ma(experiment_id)
    electrodeposition_current_ma = load_electrodeposition_current_ma(experiment_id)
    reaction_j_set = setpoint_current_density_ma_cm2(
        reaction_current_ma,
        config.electrode_area_cm2,
    )
    deposition_j_set = setpoint_current_density_ma_cm2(
        electrodeposition_current_ma,
        config.electrode_area_cm2,
    )

    lsv_traces = safe_result(
        {},
        "LSV traces",
        load_lsv_traces,
        experiment_id,
        folder_electrosynthesis,
    )
    prerx_ocp = safe_result(
        None,
        "before-reaction OCP trace",
        load_single_trace,
        experiment_id,
        folder_electrosynthesis,
        "cell*_method_OCP_prerx*.csv",
        "Before reaction OCP",
    )
    postrx_ocp = safe_result(
        None,
        "after-reaction OCP trace",
        load_single_trace,
        experiment_id,
        folder_electrosynthesis,
        "cell*_method_OCP_postrx*.csv",
        "After reaction OCP",
    )
    metric_rows = safe_result(
        empty_metric_rows(),
        "LSV and C_DL metrics",
        build_lsv_metric_rows,
        experiment_id,
        lsv_traces,
        folder_electrosynthesis,
        prerx_ocp=prerx_ocp,
        postrx_ocp=postrx_ocp,
        ph=ph,
        ref_offset_v=ref_offset_v,
        config=config,
    )
    spectra = safe_result(
        [],
        "UV-Vis spectra",
        load_uvvis_spectra,
        experiment_id,
        folder_uvvis,
        config.uvvis_plot_min_nm,
        config.uvvis_plot_max_nm,
    )
    fe_rows = safe_result(
        format_fe_table_rows([]),
        "FE rows",
        lambda: format_fe_table_rows(
            build_fe_interval_breakdowns(
                experiment_id,
                folder_uvvis,
                folder_electrosynthesis,
                config=config,
            )
        ),
    )
    reaction_trace = safe_result(
        None,
        "reaction CP/CA trace",
        load_reaction_trace,
        experiment_id,
        folder_electrosynthesis,
    )
    electrodeposition_cp = safe_result(
        None,
        "electrodeposition CP trace",
        load_single_trace,
        experiment_id,
        folder_electrodeposition,
        "cell*_method_CP*.csv",
        "Electrodeposition CP",
    )
    electrodissolution_ocp = safe_result(
        None,
        "electrodissolution OCP trace",
        load_single_trace,
        experiment_id,
        folder_electrodissolution,
        "cell*_method_OCP*.csv",
        "Electrodissolution OCP",
    )

    fig, axes = plt.subplots(2, 3, figsize=(20, 11), constrained_layout=True)

    table_spec = axes[0, 0].get_subplotspec()
    axes[0, 0].remove()
    table_grid = table_spec.subgridspec(2, 1, hspace=0.08, height_ratios=[3, 4])
    ax_composition = fig.add_subplot(table_grid[0, 0])
    ax_metrics = fig.add_subplot(table_grid[1, 0])

    safe_plot_panel(
        ax_composition,
        f"ID{experiment_id} compositions",
        "Composition metadata unavailable",
        plot_composition_table,
        experiment_id,
        catalyst_text,
        electrolyte_text,
    )
    safe_plot_panel(
        ax_metrics,
        f"ID{experiment_id} metrics",
        "Metrics unavailable",
        plot_metrics_table,
        experiment_id,
        metric_rows,
    )
    safe_plot_panel(
        axes[0, 1],
        f"ID{experiment_id} UV-Vis absorbance",
        "UV-Vis or FE data unavailable",
        plot_absorbance_with_fe,
        spectra,
        fe_rows,
        experiment_id,
        wavelength_min_nm=config.uvvis_plot_min_nm,
        wavelength_max_nm=config.uvvis_plot_max_nm,
    )
    safe_plot_panel(
        axes[0, 2],
        "OCP before/after reaction",
        "No reaction OCP files found",
        plot_ocp_overlay_panel,
        prerx_ocp,
        postrx_ocp,
        ph,
        ref_offset_v,
    )
    safe_plot_panel(
        axes[1, 0],
        "LSV before/after reaction",
        "No LSV files found",
        plot_lsv_panel,
        lsv_traces,
        ph=ph,
        ref_offset_v=ref_offset_v,
        config=config,
    )
    safe_plot_panel(
        axes[1, 1],
        "Reaction CP/CA",
        "No Reaction CP or CA file found",
        plot_reaction_trace_panel,
        reaction_trace,
        ph=ph,
        ref_offset_v=ref_offset_v,
        j_set_ma_cm2=reaction_j_set,
        config=config,
    )

    nested_spec = axes[1, 2].get_subplotspec()
    axes[1, 2].remove()
    nested_grid = nested_spec.subgridspec(2, 1, hspace=0.06)
    ax_deposition = fig.add_subplot(nested_grid[0, 0])
    ax_dissolution = fig.add_subplot(nested_grid[1, 0])
    safe_plot_panel(
        ax_deposition,
        "Electrodeposition CP",
        "No Electrodeposition CP file found",
        plot_cp_panel,
        electrodeposition_cp,
        "Electrodeposition CP",
        ph=ph,
        ref_offset_v=ref_offset_v,
        show_current=True,
        j_set_ma_cm2=deposition_j_set,
        config=config,
    )
    safe_plot_panel(
        ax_dissolution,
        "Electrodissolution OCP",
        "No Electrodissolution OCP file found",
        plot_cp_panel,
        electrodissolution_ocp,
        "Electrodissolution OCP",
        ph=ph,
        ref_offset_v=ref_offset_v,
    )

    fig.suptitle(f"Experiment ID{experiment_id} summary", fontsize=TITLE_FONT_SIZE + 2)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    for experiment_id in range(170, 179):
        saved = plot_single_experiment_summary(experiment_id)
        print(f"Saved plot: {saved}")

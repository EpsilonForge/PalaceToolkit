from pathlib import Path

import numpy as np

from palacetoolkit.postpro_vtu import (
    build_selector_context,
    discover_paraview_datasets,
    extract_axis_slice,
    extract_slice_contours,
    load_boundary_field_data,
    load_volume_field_data,
    resolve_synced_step_indices,
)


FIXTURE_POSTPRO = Path("docs/examples/postpro/patch")
FIXTURE_CONFIG = Path("docs/examples/patch.config")

# This mapping is emitted by run_meshing_pipeline for the patch example.
PATCH_PG_MAP = {
    "air_sphere": 1,
    "substrate": 2,
    "top_conductor": 3,
    "ground_plane": 4,
    "lumped_port": 5,
    "air_sphere__None": 6,
    "air_sphere__substrate": 7,
}


def test_discover_paraview_datasets_patch_fixture():
    datasets = discover_paraview_datasets(FIXTURE_POSTPRO)
    assert "driven" in datasets
    assert "driven_boundary" in datasets
    assert datasets["driven_boundary"].kind == "boundary"
    assert len(datasets["driven_boundary"].steps) > 0


def test_strict_boundary_rejects_volume_dataset():
    ctx = build_selector_context(FIXTURE_CONFIG, PATCH_PG_MAP)

    try:
        load_boundary_field_data(
            FIXTURE_POSTPRO,
            ctx,
            entity_names="lumped_port",
            dataset_name="driven",
            step_index=0,
            strict_boundary=True,
        )
        assert False, "Expected strict boundary mode to reject volume dataset"
    except ValueError as exc:
        assert "Strict boundary mode" in str(exc)


def test_load_boundary_for_entity_selector():
    ctx = build_selector_context(FIXTURE_CONFIG, PATCH_PG_MAP)

    data = load_boundary_field_data(
        FIXTURE_POSTPRO,
        ctx,
        entity_names="lumped_port",
        dataset_name="driven_boundary",
        step_index=0,
        strict_boundary=True,
    )

    assert data.selected_attributes == (5,)
    attrs = np.asarray(data.mesh.cell_data["attribute"]).astype(int)
    assert set(np.unique(attrs).tolist()) == {5}
    assert "E_real" in data.point_arrays
    assert "S" in data.point_arrays


def test_load_boundary_for_boundary_type_selector():
    ctx = build_selector_context(FIXTURE_CONFIG, PATCH_PG_MAP)

    data = load_boundary_field_data(
        FIXTURE_POSTPRO,
        ctx,
        boundary_type="PEC",
        dataset_name="driven_boundary",
        step_index=0,
        strict_boundary=True,
    )

    assert data.selected_attributes == (3, 4)
    attrs = np.asarray(data.mesh.cell_data["attribute"]).astype(int)
    assert set(np.unique(attrs).tolist()).issubset({3, 4})


def test_strict_volume_rejects_boundary_dataset():
    try:
        load_volume_field_data(
            FIXTURE_POSTPRO,
            dataset_name="driven_boundary",
            step_index=0,
            strict_volume=True,
        )
        assert False, "Expected strict volume mode to reject boundary dataset"
    except ValueError as exc:
        assert "Strict volume mode" in str(exc)


def test_load_volume_and_extract_cutplane():
    data = load_volume_field_data(
        FIXTURE_POSTPRO,
        dataset_name="driven",
        step_index=0,
        strict_volume=True,
    )
    assert "E_real" in data.point_arrays

    cut = extract_axis_slice(data, axis="z", value=0.0)
    assert cut.n_cells > 0
    assert "E_real" in cut.point_data


def test_extract_contours_from_slice():
    data = load_volume_field_data(FIXTURE_POSTPRO, dataset_name="driven", step_index=0)
    cut = extract_axis_slice(data, axis="z", value=0.0)
    cont = extract_slice_contours(cut, scalar_field="U_e", n_contours=8)
    assert cont.n_cells > 0


def test_resolve_synced_step_indices_by_timestep():
    bidx, vidx = resolve_synced_step_indices(
        FIXTURE_POSTPRO,
        boundary_dataset="driven_boundary",
        volume_dataset="driven",
        timestep=12.0,
    )
    assert isinstance(bidx, int)
    assert isinstance(vidx, int)
    assert bidx >= 0
    assert vidx >= 0

import re
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyvista as pv
from scipy.spatial import Delaunay
from scipy.interpolate import griddata

def clean_column(name: str) -> str:
    name = re.sub(r"\s*\([^)]*\)", "", name)
    return name.strip()

def compute_field_magnitude(df: pd.DataFrame) -> np.ndarray:
    Ex_re = df["r*Re{E_x}"].to_numpy(float)
    Ex_im = df["r*Im{E_x}"].to_numpy(float)
    Ey_re = df["r*Re{E_y}"].to_numpy(float)
    Ey_im = df["r*Im{E_y}"].to_numpy(float)
    Ez_re = df["r*Re{E_z}"].to_numpy(float)
    Ez_im = df["r*Im{E_z}"].to_numpy(float)
    return np.sqrt(
        Ex_re**2 + Ex_im**2 +
        Ey_re**2 + Ey_im**2 +
        Ez_re**2 + Ez_im**2
    )


def compute_db(magnitude: np.ndarray, floor_db: float = -25.0) -> np.ndarray:
    """Normalize to 0 dB max, clip at floor_db."""
    mag = np.maximum(magnitude, np.max(magnitude) * 1e-10)
    db = 20.0 * np.log10(mag)
    db -= np.max(db)
    return np.clip(db, floor_db, 0.0)


def extract_eplane(df: pd.DataFrame, tolerance_deg: float = 5.0) -> dict:
    phi = df["phi"].to_numpy(float)
    result = {}

    # half1: phi~0°, theta 0->180 maps to polar angle 0->180
    mask1 = np.abs(phi - 0.0) < tolerance_deg
    if np.any(mask1):
        d1 = df.loc[mask1]
        a1 = d1["theta"].to_numpy(float)          # 0° → 180°
        m1 = compute_field_magnitude(d1)
        idx = np.argsort(a1)
        result["half1"] = (a1[idx], m1[idx])
        print(f"  E-plane phi~0°:   {mask1.sum()} points")

    # half2: phi~180°, theta 0->180 maps to polar angle 180->360
    mask2 = np.abs(phi - 180.0) < tolerance_deg
    if np.any(mask2):
        d2 = df.loc[mask2]
        a2 = 180.0 + d2["theta"].to_numpy(float)  # 180° → 360°
        m2 = compute_field_magnitude(d2)
        idx = np.argsort(a2)
        result["half2"] = (a2[idx], m2[idx])
        print(f"  E-plane phi~180°: {mask2.sum()} points")

    return result


def extract_hplane(df: pd.DataFrame, tolerance_deg: float = 5.0):
    """H-plane (xy-plane): theta ~ 90°."""
    theta = df["theta"].to_numpy(float)
    mask  = np.abs(theta - 90.0) < tolerance_deg
    d     = df.loc[mask]
    print(f"  H-plane theta~90°: {mask.sum()} points")
    if mask.sum() == 0:
        print("  WARNING: No H-plane points found, try increasing tolerance_deg")
        return np.array([]), np.array([])
    return d["phi"].to_numpy(float), compute_field_magnitude(d)


def style_polar_ax(ax, title: str, db_min: float = -25.0):
    ax.set_title(title, pad=12)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(db_min, 2)
    ax.set_rticks(np.arange(db_min, 1, 5))
    ax.set_rlabel_position(45)
    ax.grid(True, color="lightgray", linewidth=0.8)

def polar_plots(
    df: pd.DataFrame,
    label: str,
    db_min: float = -25.0,
):
    print("Extracting E-plane...")
    e_data = extract_eplane(df)
    print("Extracting H-plane...")
    h_angles, h_mag = extract_hplane(df)

    fig = plt.figure(figsize=(11, 5))

    # ── E-plane ──────────────────────────────────────────────────────
    ax1 = fig.add_subplot(1, 2, 1, projection="polar")
    style_polar_ax(ax1, f"E-plane ({label})", db_min)

    if e_data:
        parts_angles = []
        parts_mags   = []

        if "half1" in e_data:
            a, m = e_data["half1"]
            parts_angles.append(a)
            parts_mags.append(m)

        if "half2" in e_data:
            a, m = e_data["half2"]
            parts_angles.append(a)   # already sorted 180->360, no reversal needed
            parts_mags.append(m)

        if parts_angles:
            # Combine and sort (0 -> 360)
            all_angles = np.concatenate(parts_angles)
            all_mags   = np.concatenate(parts_mags)
            sort_idx   = np.argsort(all_angles)
            all_angles = all_angles[sort_idx]
            all_mags   = all_mags[sort_idx]

            # Normalize globally so both halves share the same 0 dB reference
            db = compute_db(all_mags, db_min)

            # Close the loop only if data actually spans ~360 degrees
            if abs(all_angles[-1] - all_angles[0] - 360) < 10:
                plot_angles = np.append(all_angles, all_angles[0] + 360)
                plot_db     = np.append(db, db[0])
            else:
                plot_angles = all_angles
                plot_db     = db

            ax1.plot(np.deg2rad(plot_angles), plot_db, linewidth=2, color="tab:blue")
            ax1.scatter(np.deg2rad(all_angles), db, s=18, color="tab:blue", zorder=5)
        else:
            ax1.text(0.5, 0.5, "No E-plane points found",
                        transform=ax1.transAxes, ha="center", va="center")
    # ── H-plane ──────────────────────────────────────────────────────
    ax2 = fig.add_subplot(1, 2, 2, projection="polar")
    style_polar_ax(ax2, f"H-plane ({label})", db_min)

    if h_mag.size > 1:
        h_db            = compute_db(h_mag, db_min)
        sort_idx        = np.argsort(h_angles)
        h_angles_sorted = h_angles[sort_idx]
        h_db_sorted     = h_db[sort_idx]
        h_angles_closed = np.append(h_angles_sorted, h_angles_sorted[0])
        h_db_closed     = np.append(h_db_sorted,     h_db_sorted[0])
        ax2.plot(np.deg2rad(h_angles_closed), h_db_closed, linewidth=2, color="tab:blue")
        ax2.scatter(np.deg2rad(h_angles_sorted), h_db_sorted, s=18, color="tab:blue", zorder=5)
    else:
        ax2.text(0.5, 0.5, "No H-plane points found",
                 transform=ax2.transAxes, ha="center", va="center")

    fig.suptitle(label, y=1.01)
    fig.tight_layout()
    plt.show()


def three_d_plot(
    df: pd.DataFrame,
    label: str,
    n_theta: int            = 360,
    n_phi: int              = 720,
    n_smooth: int           = 100,
    taubin_pass_band: float = 0.1,
):
    E_raw     = compute_field_magnitude(df)
    if E_raw.size == 0:
        raise ValueError("No data for 3D plot.")

    theta_raw = df["theta"].to_numpy(float)
    phi_raw   = df["phi"].to_numpy(float)

    # ── 1. Interpolate onto a regular (theta, phi) grid ──────────────
    theta_lin = np.linspace(1,   179, n_theta)
    phi_lin   = np.linspace(0,   360, n_phi)
    TH, PH    = np.meshgrid(theta_lin, phi_lin, indexing="ij")

    pts_src = np.column_stack([theta_raw, phi_raw])
    E_grid  = griddata(pts_src, E_raw, (TH, PH), method="linear")

    nan_mask = np.isnan(E_grid)
    if nan_mask.any():
        E_fill           = griddata(pts_src, E_raw, (TH, PH), method="nearest")
        E_grid[nan_mask] = E_fill[nan_mask]

    E_grid /= np.max(E_grid)

    # ── 2. Wrap the φ seam ────────────────────────────────────────────
    E_wrap      = np.hstack([E_grid, E_grid[:, :1]])
    TH_w        = np.hstack([TH,     TH[:, :1]])
    PH_w        = np.hstack([PH,     PH[:, :1]])
    PH_w[:, -1] = 360.0

    # ── 3. Cartesian coordinates ──────────────────────────────────────
    TH_r = np.deg2rad(TH_w)
    PH_r = np.deg2rad(PH_w)

    X = E_wrap * np.sin(TH_r) * np.cos(PH_r)
    Y = E_wrap * np.sin(TH_r) * np.sin(PH_r)
    Z = E_wrap * np.cos(TH_r)

    # ── 4. Build StructuredGrid ───────────────────────────────────────
    grid = pv.StructuredGrid(X.T, Y.T, Z.T)
    grid["E_norm"] = E_wrap.T.ravel(order="F")

    # ── 5. Extract surface ────────────────────────────────────────────
    mesh = grid.extract_surface()

    # ── 6. Cap pole holes ─────────────────────────────────────────────
    mesh = mesh.fill_holes(hole_size=10000)

    # ── 7. Taubin smoothing ───────────────────────────────────────────
    mesh = mesh.smooth_taubin(
        n_iter=n_smooth,
        pass_band=taubin_pass_band,
        feature_smoothing=False,
        boundary_smoothing=True,
        normalize_coordinates=True,
    )

    # ── 8. Plotting (notebook) ────────────────────────────────────────
    pl = pv.Plotter(notebook=True)
    pl.set_background("white")
    pl.add_title(f"Relative E-field magnitude ({label})", font_size=12)
    pl.add_mesh(
        mesh,
        scalars="E_norm",
        cmap="viridis",
        smooth_shading=True,
        scalar_bar_args={"title": "Normalized |E|"},
    )
    pl.add_axes()
    pl.camera_position = "iso"
    pl.show()

def load_data(filename, freq):
    try:
        df = pd.read_csv(filename)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        print("Usage: python plot_farfield.py [filename]")
        return

    df = df.rename(columns={c: clean_column(c) for c in df.columns})
    print("Columns found:", list(df.columns))

    if "m" in df.columns:
        m0    = df["m"].iloc[0]
        data  = df[df["m"] == m0].copy()
        label = f"m = {m0}"
        print(f"Processing mode: {m0}  ({len(data)} rows)")
    elif "f" in df.columns:
        f0    = freq
        data  = df[df["f"] == f0].copy()
        label = f"f = {f0:.4f} GHz"
        print(f"Processing frequency: {f0} GHz  ({len(data)} rows)")
    else:
        data  = df.copy()
        label = "all data"
        print(f"No 'm' or 'f' column found; plotting all {len(data)} rows.")
    return data, label

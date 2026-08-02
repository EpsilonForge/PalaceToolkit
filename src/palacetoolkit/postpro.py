import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def _read_s_params_csv(csv_file) -> pd.DataFrame:
    """Read a Palace ``port-S.csv`` and rename columns consistently."""
    df = pd.read_csv(csv_file)
    if df.shape[1] == 5:
        df.columns = ["Freq_GHz", "S11_dB", "S11_phase_deg", "S21_dB", "S21_phase_deg"]
    else:
        df.columns = ["Freq_GHz", "S11_dB", "S11_phase_deg"]
    return df


def s_params(csv_file):
    df = _read_s_params_csv(csv_file)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["Freq_GHz"], df["S11_dB"], label="|S11| (dB)", marker='o')
    if df.shape[1] == 5:
        ax.plot(df["Freq_GHz"], df["S21_dB"], label="|S21| (dB)", marker='s')
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title("S-parameter magnitude")
    ax.grid(True)
    ax.legend()

    return fig, ax


def resonant_frequency(csv_file) -> float:
    """Return the frequency (GHz) where |S11| reaches its minimum."""
    df = _read_s_params_csv(csv_file)
    idx = np.argmin(df["S11_dB"])
    return float(df["Freq_GHz"].iloc[idx])


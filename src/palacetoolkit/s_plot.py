import pandas as pd
import matplotlib.pyplot as plt

def plot_s_params(csv_file = r"C:\Users\loloc\Desktop\Epsilon\palace-course\lecture_3_waveports\results\patch_antenna\port-S.csv"):

    df = pd.read_csv(csv_file)

    # Renombrar columnas si es necesario (según tu archivo)
    if df.shape[1] == 5:
        df.columns = ["Freq_GHz", "S11_dB", "S11_phase_deg", "S21_dB", "S21_phase_deg"]
    else:
        df.columns = ["Freq_GHz", "S11_dB", "S11_phase_deg"]

    # Plot S11, S21
    plt.figure(figsize=(10,6))
    plt.plot(df["Freq_GHz"], df["S11_dB"], label="|S11| (dB)", marker='o')
    if df.shape[1] == 5:
        plt.plot(df["Freq_GHz"], df["S21_dB"], label="|S21| (dB)", marker='s')
    plt.xlabel("Frecuencia (GHz)")
    plt.ylabel("Magnitud (dB)")
    plt.title("S parameters magnitude")
    plt.grid(True)
    plt.legend()

    plt.show()

if __name__ == "__main__":
    plot_s_params()


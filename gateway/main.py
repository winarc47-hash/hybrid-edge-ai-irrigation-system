import serial, ollama, threading, numpy as np, re, time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# --- SERIAL HUB INITIALIZATION ---
PORT = 'COM8' # <--- Linked port matching your physical ESP32 connection
ser = serial.Serial(PORT, 115200, timeout=1)

# Dynamic history data vectors for dashboard rendering
t_h, p_h, w_h, z_h, ai_h = [], [], [], [], []

def ask_ai(p_list, t_val, w_val):
    """ Executes local on-device LLM Inference to classify climate state """
    # Calculate a simple historical baseline pressure directly from the telemetry history array
    avg_p = np.mean(p_list)
    
    # --- PURE ML SYSTEM MATRIX PROMPT ---
    # We provide zero rule metrics (No hard thresholds). 
    # Llama 3.2 must use its mathematical neural weights to judge if the data means rain or fair weather.
    prompt_matrix = (
        f"METEOROLOGICAL DATASET - Temperature: {t_val}C, Barometric Pressure: {avg_p:.1f}hPa, Wind Speed: {w_val}km/h. "
        "INSTRUCTION: Evaluate these physical atmospheric variables. "
        "If indicators imply an imminent storm, low-pressure system collapse, or rain conditions, generate exactly the word STOP. "
        "If indicators imply stable, warm, or clear conditions requiring crop irrigation, generate exactly the word WATER. "
        "CRITICAL: Do not write a sentence. Do not include spaces, periods, or headers. Output ONLY the single target word choice."
    )
    
    try:
        # Querying the local neural network framework
        res = ollama.chat(model='llama3.2:1b', 
                          messages=[{'role': 'user', 'content': prompt_matrix}],
                          options={
                              'temperature': 0.0,   # Set to 0.0 to strip out random assistant behavior and enforce deterministic calculation
                              'num_predict': 3,      # Hard limitation to prevent the model from expanding beyond a single token response
                              'top_p': 0.1           # Limits distribution parameters to highest probability matches
                          })
        
        # --- PARSING AND CHARACTER CLEANUP ---
        raw_reply = res['message']['content'].strip()
        # Regex deletes hidden newline breaks, punctuation marks, or accidental symbols
        clean_reply = re.sub(r'[^a-zA-Z]', '', raw_reply).upper()
        
        # Binary Classification Mapping to ensure safe transmission down to your Pin D2 C++ Code
        if "WATER" in clean_reply:
            decision = "WATER"
            graph_plot_index = 10  # Plotted on your dashboard as low risk
            final_msg = f"10%, CLEAR AIR. {decision}"
        else:
            decision = "STOP"
            graph_plot_index = 90  # Plotted on your dashboard as anomaly alert threshold
            final_msg = f"90%, STORM INCOMING. {decision}"
            
            # Additional safety: scrub 'WATER' out completely on rain cycles
            final_msg = final_msg.replace("WATER", "SHUTDOWN")

        # Push calculated state level to the dashboard graph array
        ai_h.append(graph_plot_index)
        
        # Transmit the data package to the serial line. It terminates with \n so ESP32 knows it's ready.
        ser.write((final_msg + "\n").encode())
        print(f"Pure AI Output: {final_msg} (Raw Model Word: '{raw_reply}')")
        
    except Exception as e:
        # Critical background failsafe if Ollama server hits background lag
        print(f"AI Error: {e}")
        ser.write("10%, AI Sync. STOP\n".encode())

# --- REAL-TIME GRAPH RENDERING ENGINE (UNTOUCHED) ---
plt.style.use('dark_background') 
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(11, 8))
plt.subplots_adjust(left=0.1, bottom=0.15, right=0.9, top=0.9, wspace=0.3, hspace=0.5)

def update(frame):
    if ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line.count(",") == 3:
            try:
                t, p, w, z = map(float, line.split(","))
                t_h.append(t); p_h.append(p); w_h.append(w); z_h.append(z)

                ax1.cla(); ax1.plot(t_h[-20:], p_h[-20:], 'c-o'); ax1.set_title("Environment Air Trend")
                
                ax2.cla(); ax2.fill_between(range(len(z_h[-20:])), z_h[-20:], color='blue', alpha=0.3); ax2.set_title("Local Risk %")
                
                # Noise filter for 500k Pot (Subtracting 41 baseline noise)
                ax3.cla(); ax3.bar(range(len(w_h[-20:])), [max(0, v-41) for v in w_h[-20:]], color='orange'); ax3.set_title("Wind Sensor (km/h)")
                
                ax4.cla(); ax4.step(range(len(ai_h)), ai_h, color='red', where='post', linewidth=3); ax4.set_title("AI Forecast Risk %")

                if len(p_h) > 0 and len(p_h) % 10 == 0:
                    threading.Thread(target=ask_ai, args=(p_h[-10:], t, w)).start()

# Infinite loop listener bound to standard 2-second hardware cycles
ani = FuncAnimation(fig, update, interval=2000, cache_frame_data=False)
plt.show()

import argparse
import pretty_midi
import random
import math

def thicken_melody(midi_inst, add_lower_octave=True):
    # ... (Logika sama: Octave Doubling) ...
    print("   💪 Menebalkan Vokal (Conditional Octave Doubling)...")
    original_notes = sorted(midi_inst.notes, key=lambda x: x.start)
    thickened_notes = []
    if not original_notes: return midi_inst

    def process_cluster(cluster):
        should_double = add_lower_octave and (len(cluster) < 3)
        for note in cluster:
            thickened_notes.append(note) 
            if should_double:
                shadow_pitch = note.pitch - 12
                if shadow_pitch >= 48: 
                    shadow_note = pretty_midi.Note(
                        velocity=max(40, note.velocity - 15), 
                        pitch=shadow_pitch, start=note.start, end=note.end
                    )
                    thickened_notes.append(shadow_note)

    current_cluster = [original_notes[0]]
    for i in range(1, len(original_notes)):
        note = original_notes[i]
        prev_note = original_notes[i-1]
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            process_cluster(current_cluster)
            current_cluster = [note]
    if current_cluster: process_cluster(current_cluster)
    thickened_notes.sort(key=lambda x: x.start)
    midi_inst.notes = thickened_notes
    return midi_inst

def select_best_notes(cluster, limit, keep_middle):
    # ... (Logika sama: Memilih not terbaik) ...
    if len(cluster) <= limit: return cluster
    cluster.sort(key=lambda x: x.pitch)
    selected_notes = []
    indices_taken = set()
    if limit >= 1:
        selected_notes.append(cluster[0])
        indices_taken.add(0)
    if limit >= 2:
        last_idx = len(cluster) - 1
        if last_idx not in indices_taken:
            selected_notes.append(cluster[last_idx])
            indices_taken.add(last_idx)
    slots_left = limit - len(selected_notes)
    if slots_left > 0:
        middle_candidates = []
        for i in range(len(cluster)):
            if i not in indices_taken: middle_candidates.append(cluster[i])
        if keep_middle: middle_candidates.sort(key=lambda x: x.end - x.start, reverse=True)
        selected_notes.extend(middle_candidates[:slots_left])
    selected_notes.sort(key=lambda x: x.pitch)
    return selected_notes

def smart_simplify_instrument(midi_inst, vocal_inst, max_poly_active=3, max_poly_idle=10, global_finger_limit=10, min_duration=0.1):
    # ... (Logika sama: Filter Polyphony) ...
    print(f"   🧠 Smart Dynamic Filter (Global Limit: {global_finger_limit} jari)...")
    vocal_intervals = []
    buffer = 0.1 
    for vn in vocal_inst.notes:
        vocal_intervals.append((vn.start - buffer, vn.end + buffer))
    playable_notes = [n for n in midi_inst.notes if (n.end - n.start) >= min_duration]
    path_notes = sorted(playable_notes, key=lambda x: x.start)
    final_notes = []
    if not path_notes:
        midi_inst.notes = []
        return midi_inst
    current_cluster = [path_notes[0]]
    
    def get_realtime_limit(cluster_start_time):
        active_vocal_count = 0
        for v_start, v_end in vocal_intervals:
            if v_start <= cluster_start_time <= v_end: active_vocal_count += 1
        target_limit = max_poly_active if active_vocal_count > 0 else max_poly_idle
        remaining = global_finger_limit - active_vocal_count
        return min(target_limit, max(1, remaining))

    for i in range(1, len(path_notes)):
        note = path_notes[i]
        prev_note = path_notes[i-1]
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            limit = get_realtime_limit(current_cluster[0].start)
            final_notes.extend(select_best_notes(current_cluster, limit, False))
            current_cluster = [note]
    if current_cluster:
        limit = get_realtime_limit(current_cluster[0].start)
        final_notes.extend(select_best_notes(current_cluster, limit, False))
    midi_inst.notes = final_notes
    return midi_inst

def adjust_track(midi_data, velocity, octave_shift, name):
    new_inst = pretty_midi.Instrument(program=0, name=name)
    if len(midi_data.instruments) > 0:
        source_inst = midi_data.instruments[0]
        for note in source_inst.notes:
            shifted_pitch = note.pitch + (octave_shift * 12)
            if 0 <= shifted_pitch <= 127:
                new_note = pretty_midi.Note(
                    velocity=velocity, pitch=shifted_pitch, start=note.start, end=note.end
                )
                new_inst.notes.append(new_note)
        # COPY PEDAL & BEND (Wajib agar tidak kering)
        new_inst.control_changes = source_inst.control_changes[:]
        new_inst.pitch_bends = source_inst.pitch_bends[:]
    return new_inst

def remove_conflicts_smart(melody_inst, chord_inst, time_tolerance=0.05, pitch_safety_gap=12):
    # ... (Logika sama: Hapus tabrakan frekuensi) ...
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Smart Conflict Resolution...")
    m_idx = 0
    total_melody = len(melody_notes)
    for c_note in chord_inst.notes:
        should_remove = False
        while m_idx < total_melody and melody_notes[m_idx].end < c_note.start - time_tolerance:
            m_idx += 1
        for i in range(m_idx, total_melody):
            m_note = melody_notes[i]
            if m_note.start > c_note.start + time_tolerance: break 
            if abs(c_note.start - m_note.start) <= time_tolerance:
                if abs(c_note.pitch - m_note.pitch) < pitch_safety_gap:
                    should_remove = True
                    break
        if not should_remove: cleaned_chord_notes.append(c_note)
    chord_inst.notes = cleaned_chord_notes
    return chord_inst

# ==========================================
# 🔥 FITUR BARU: LEGATO STITCHING 🔥
# ==========================================
def apply_smart_legato(midi_inst, max_gap_threshold=0.4):
    """
    Fungsi Penjahit: Menyambungkan not yang terputus akibat simplifikasi.
    Jika ada celah kosong (silence) < 0.4 detik antara satu not dengan not berikutnya,
    not pertama akan dipanjangin (sustain) sampai menyentuh not berikutnya.
    """
    print("   🔗 Menjahit Not yang Terputus (Legato Fix)...")
    notes = sorted(midi_inst.notes, key=lambda x: x.start)
    if not notes: return midi_inst
    
    # Kita iterasi dan cari not terdekat berikutnya
    for i in range(len(notes) - 1):
        curr_note = notes[i]
        
        # Cari not berikutnya yang start-nya > start saat ini (bukan chord yang sama)
        next_idx = i + 1
        while next_idx < len(notes):
            if notes[next_idx].start > curr_note.start + 0.05:
                break
            next_idx += 1
            
        if next_idx < len(notes):
            next_note = notes[next_idx]
            gap = next_note.start - curr_note.end
            
            # Jika ada gap kecil (suara putus tiba-tiba), kita tambal
            if 0 < gap < max_gap_threshold:
                # Panjangkan not sekarang sampai sedikit overlap dengan not depan
                curr_note.end = next_note.start + 0.05 

    midi_inst.notes = notes
    return midi_inst

def humanize_performance(midi_inst, strum_speed=0.015, timing_jitter=0.01, velocity_sigma=5):
    """
    Humanize dengan proteksi durasi agar tidak menjadi staccato.
    """
    print(f"   ❤️  Applying Human Touch...")
    notes = sorted(midi_inst.notes, key=lambda x: x.start)
    if not notes: return midi_inst
    humanized_notes = []
    current_cluster = [notes[0]]
    
    def process_human_cluster(cluster):
        cluster.sort(key=lambda x: x.pitch)
        cluster_size = len(cluster)
        for idx, note in enumerate(cluster):
            strum_delay = 0
            if cluster_size > 1: strum_delay = idx * strum_speed 
            
            start_drift = random.uniform(-timing_jitter, timing_jitter)
            # Release drift selalu positif (memanjang) untuk keamanan legato
            end_drift = random.uniform(0, timing_jitter * 4) 
            
            new_start = max(0, note.start + strum_delay + start_drift)
            # Pastikan not tidak jadi terlalu pendek (Min 0.2s)
            min_dur = 0.2 
            new_end = max(new_start + min_dur, note.end + strum_delay + end_drift)
            
            melody_accent = 5 if idx == cluster_size - 1 and cluster_size > 1 else 0
            base_vel = note.velocity
            random_vel = int(random.gauss(0, velocity_sigma))
            final_vel = max(10, min(120, base_vel + random_vel + melody_accent))
            
            human_note = pretty_midi.Note(
                velocity=final_vel, pitch=note.pitch, start=new_start, end=new_end
            )
            humanized_notes.append(human_note)

    for i in range(1, len(notes)):
        note = notes[i]
        prev_note = notes[i-1]
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            process_human_cluster(current_cluster)
            current_cluster = [note]
    if current_cluster: process_human_cluster(current_cluster)
        
    humanized_notes.sort(key=lambda x: x.start)
    midi_inst.notes = humanized_notes
    return midi_inst

def main():
    parser = argparse.ArgumentParser(description="MIDI Grand Piano Processor (Final Fix)")
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_clean.mid")
    
    parser.add_argument("--double_vocal", action='store_true', default=True)
    parser.add_argument("--max_poly", type=int, default=3)
    
    parser.add_argument("--vol_vocal", type=int, default=95)
    parser.add_argument("--vol_instr", type=int, default=80)
    parser.add_argument("--shift_vocal", type=int, default=0)
    parser.add_argument("--shift_instr", type=int, default=-1)
    parser.add_argument("--min_dur", type=float, default=0.1)
    
    parser.add_argument("--strum", type=float, default=0.012)
    parser.add_argument("--jitter", type=float, default=0.015)
    parser.add_argument("--vel_var", type=int, default=8)

    args = parser.parse_args()

    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"❌ Error loading MIDI: {e}")
        return

    print("🎹 Processing Grand Piano (Legato Stitching Mode)...")

    # 1. Adjust & Copy Pedal
    vocal_track = adjust_track(pm_vocal, args.vol_vocal, args.shift_vocal, "Melody")
    instr_track = adjust_track(pm_instr, args.vol_instr, args.shift_instr, "Accompaniment")

    # 2. Logic Struktur
    if args.double_vocal:
        vocal_track = thicken_melody(vocal_track)

    instr_track = smart_simplify_instrument(
        instr_track, vocal_track,
        max_poly_active=args.max_poly, max_poly_idle=10, min_duration=args.min_dur
    )

    instr_track = remove_conflicts_smart(vocal_track, instr_track)

    # 3. [PENTING] JAHIT NOT YANG TERPUTUS SEBELUM HUMANIZE
    # Ini mengisi celah kosong akibat simplifikasi agar tidak 'berhenti tiba-tiba'
    instr_track = apply_smart_legato(instr_track, max_gap_threshold=0.5)

    # 4. Humanize
    print("\n   --- TAHAP AKHIR: MEMANUSIAKAN ---")
    vocal_track = humanize_performance(vocal_track, strum_speed=0.005, timing_jitter=args.jitter)
    instr_track = humanize_performance(instr_track, strum_speed=args.strum, timing_jitter=args.jitter)

    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! Output: {args.output}")

if __name__ == "__main__":
    main()

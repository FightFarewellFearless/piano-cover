import argparse
import pretty_midi
import random

# ==========================================
# MODUL HUMANIZER (PHYSICS)
# ==========================================
def apply_human_physics(midi_inst, instrument_type="piano"):
    """
    Mengubah data MIDI yang kaku (robotik) menjadi lebih manusiawi.
    Fitur: Jitter, Velocity Randomization, Strumming, Legato.
    """
    print(f"   ✨ Applying Human Physics to {instrument_type}...")
    
    notes = midi_inst.notes
    if not notes:
        return midi_inst

    # Sortir not berdasarkan waktu
    notes.sort(key=lambda x: x.start)

    # Konfigurasi Human Feel
    if instrument_type == "vocal":
        timing_jitter = 0.015  # +/- 15ms
        vel_sigma = 8          
        strum_speed = 0        
    else:
        timing_jitter = 0.02   # +/- 20ms
        vel_sigma = 12         
        strum_speed = 0.015    # 15ms strumming
    
    # Grouping untuk Strumming Logic
    clusters = []
    if notes:
        current_cluster = [notes[0]]
        for i in range(1, len(notes)):
            if abs(notes[i].start - notes[i-1].start) < 0.01:
                current_cluster.append(notes[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [notes[i]]
        clusters.append(current_cluster)

    final_notes = []

    for cluster in clusters:
        cluster.sort(key=lambda x: x.pitch)
        cluster_size = len(cluster)
        is_strum = cluster_size > 1 and instrument_type != "vocal"
        
        for i, note in enumerate(cluster):
            # A. RANDOM TIMING (Jitter)
            random_offset = random.gauss(0, timing_jitter)
            
            # B. STRUMMING OFFSET (Efek kunci untuk piano natural)
            strum_offset = 0
            if is_strum:
                strum_offset = (i * strum_speed) + random.uniform(0, 0.005)

            new_start = note.start + random_offset + strum_offset
            
            # C. LEGATO & DURATION
            duration_stretch = random.uniform(0, 0.05) 
            new_end = note.end + random_offset + strum_offset + duration_stretch

            if new_start < 0: new_start = 0
            if new_end <= new_start: new_end = new_start + 0.1

            note.start = new_start
            note.end = new_end

            # D. VELOCITY HUMANIZATION
            vel_random = int(random.gauss(0, vel_sigma))
            accent = 0
            if cluster_size > 1:
                if i == 0: accent = 5 # Bass
                if i == cluster_size - 1: accent = 8 # Melodi
            
            new_vel = note.velocity + vel_random + accent
            new_vel = max(1, min(127, new_vel))
            note.velocity = new_vel
            
            final_notes.append(note)

    midi_inst.notes = final_notes
    return midi_inst

# ==========================================
# FUNGSI LOGIKA UTAMA
# ==========================================

def thicken_melody(midi_inst, add_lower_octave=True):
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
                    # Delay sedikit agar tidak phase cancellation
                    delay = random.uniform(0.010, 0.020) 
                    shadow_note = pretty_midi.Note(
                        velocity=max(40, note.velocity - 15), 
                        pitch=shadow_pitch,
                        start=note.start + delay,
                        end=note.end + delay
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
    if len(cluster) <= limit: return cluster
    cluster.sort(key=lambda x: x.pitch)
    selected_notes = []
    indices_taken = set()
    
    # Bass & Top Note priority
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
            if i not in indices_taken:
                middle_candidates.append(cluster[i])
        if keep_middle:
            middle_candidates.sort(key=lambda x: x.end - x.start, reverse=True)
        selected_notes.extend(middle_candidates[:slots_left])

    selected_notes.sort(key=lambda x: x.pitch)
    return selected_notes

def smart_simplify_instrument(midi_inst, vocal_inst, max_poly_active=3, max_poly_idle=10, global_finger_limit=10, min_duration=0.1):
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
        is_vocal_active = False
        for v_start, v_end in vocal_intervals:
            if v_start <= cluster_start_time <= v_end:
                active_vocal_count += 1
                is_vocal_active = True
        target_limit = max_poly_active if is_vocal_active else max_poly_idle
        remaining_fingers = global_finger_limit - active_vocal_count
        if remaining_fingers < 1: remaining_fingers = 1
        return min(target_limit, remaining_fingers)

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
        for note in midi_data.instruments[0].notes:
            shifted_pitch = note.pitch + (octave_shift * 12)
            if 0 <= shifted_pitch <= 127:
                new_note = pretty_midi.Note(
                    velocity=velocity, pitch=shifted_pitch, start=note.start, end=note.end
                )
                new_inst.notes.append(new_note)
    return new_inst

def remove_conflicts_smart(melody_inst, chord_inst, time_tolerance=0.05, pitch_safety_gap=12):
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Smart Conflict Resolution (Proteksi Bass, Tol: {time_tolerance}s)...")
    removed_count = 0
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
        if should_remove: removed_count += 1
        else: cleaned_chord_notes.append(c_note)
    
    print(f"      -> Dihapus {removed_count} not yang menabrak frekuensi vokal.")
    chord_inst.notes = cleaned_chord_notes
    return chord_inst

def main():
    parser = argparse.ArgumentParser(description="Humanized Grand Piano Processor")
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    
    # -----------------------------------------------
    # OUTPUT FILE DEFAULT diganti ke "final_clean.mid"
    # -----------------------------------------------
    parser.add_argument("--output", default="final_clean.mid")
    
    # Feature Toggles
    parser.add_argument("--double_vocal", action='store_true', default=True)
    parser.add_argument("--max_poly", type=int, default=3)
    parser.add_argument("--humanize", action='store_true', default=True, help="Aktifkan efek humanisasi")

    args = parser.parse_args()

    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"❌ Error loading MIDI: {e}")
        return

    print("🎹 Processing Grand Piano Effect...")

    # 1. Adjust Basic
    vocal_track = adjust_track(pm_vocal, 100, 0, "Melody")
    instr_track = adjust_track(pm_instr, 85, -1, "Accompaniment")

    # 2. THICKEN VOCAL
    if args.double_vocal:
        vocal_track = thicken_melody(vocal_track)

    # 3. SMART DYNAMIC FILTER
    instr_track = smart_simplify_instrument(
        instr_track, 
        vocal_track,
        max_poly_active=args.max_poly,
        max_poly_idle=10
    )

    # 4. SMART CONFLICT
    instr_track = remove_conflicts_smart(vocal_track, instr_track, time_tolerance=0.1, pitch_safety_gap=15)

    # 5. HUMANIZATION
    if args.humanize:
        vocal_track = apply_human_physics(vocal_track, instrument_type="vocal")
        instr_track = apply_human_physics(instr_track, instrument_type="piano")

    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! Output: {args.output}")

if __name__ == "__main__":
    main()

import argparse
import pretty_midi

def thicken_melody(midi_inst, add_lower_octave=True):
    """
    FITUR: Menebalkan melodi vokal (Octave Doubling).
    UPDATE: Logic Conditional Doubling.
    - Jika not dipukul bersamaan < 3 (Solo/Dyad) -> Lakukan Octave Doubling.
    - Jika not dipukul bersamaan >= 3 (Chord) -> Biarkan murni (tanpa double).
    """
    print("   💪 Menebalkan Vokal (Conditional Octave Doubling)...")
    
    # 1. Sortir not berdasarkan waktu agar pengelompokan akurat
    original_notes = sorted(midi_inst.notes, key=lambda x: x.start)
    thickened_notes = []
    
    if not original_notes:
        return midi_inst

    # Fungsi internal untuk memproses satu kelompok not (chord)
    def process_cluster(cluster):
        # Cek kondisi: Hanya double jika jumlah not dalam cluster < 3
        should_double = add_lower_octave and (len(cluster) < 3)
        
        for note in cluster:
            thickened_notes.append(note) # Selalu simpan not asli
            
            if should_double:
                shadow_pitch = note.pitch - 12
                # Pastikan tidak terlalu rendah (limit di pitch 48 / C3)
                if shadow_pitch >= 48: 
                    shadow_note = pretty_midi.Note(
                        velocity=max(40, note.velocity - 15), # Velocity bayangan lebih kecil
                        pitch=shadow_pitch,
                        start=note.start,
                        end=note.end
                    )
                    thickened_notes.append(shadow_note)

    # 2. Algoritma Clustering (Mengelompokkan not yang main bareng)
    current_cluster = [original_notes[0]]
    
    for i in range(1, len(original_notes)):
        note = original_notes[i]
        prev_note = original_notes[i-1]
        
        # Jika selisih waktu sangat kecil (< 50ms), anggap satu chord
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            # Waktu sudah geser, proses cluster sebelumnya
            process_cluster(current_cluster)
            # Reset untuk cluster baru
            current_cluster = [note]
            
    # Jangan lupa proses cluster terakhir yang tertinggal di memori
    if current_cluster:
        process_cluster(current_cluster)
    
    # Sortir ulang hasil akhir untuk keamanan urutan MIDI
    thickened_notes.sort(key=lambda x: x.start)
    midi_inst.notes = thickened_notes
    return midi_inst

def select_best_notes(cluster, limit, keep_middle):
    """
    Memilih not terbaik dari accompaniment berdasarkan limit polyphony.
    """
    if len(cluster) <= limit:
        return cluster
    
    cluster.sort(key=lambda x: x.pitch)
    selected_notes = []
    indices_taken = set()
    
    # 1. BASS (Wajib - Fondasi)
    if limit >= 1:
        selected_notes.append(cluster[0])
        indices_taken.add(0)
    
    # 2. TOP NOTE (Wajib - Melodi Instrumen)
    if limit >= 2:
        last_idx = len(cluster) - 1
        if last_idx not in indices_taken:
            selected_notes.append(cluster[last_idx])
            indices_taken.add(last_idx)

    # 3. MIDDLE FILLER (Isian)
    slots_left = limit - len(selected_notes)
    if slots_left > 0:
        middle_candidates = []
        for i in range(len(cluster)):
            if i not in indices_taken:
                middle_candidates.append(cluster[i])
        
        # Prioritaskan not panjang jika keep_middle aktif
        if keep_middle:
            middle_candidates.sort(key=lambda x: x.end - x.start, reverse=True)
            
        selected_notes.extend(middle_candidates[:slots_left])

    selected_notes.sort(key=lambda x: x.pitch)
    return selected_notes

def smart_simplify_instrument(midi_inst, vocal_inst, max_poly_active=3, max_poly_idle=10, min_duration=0.1):
    """
    Dynamic Polyphony:
    - Vokal AKTIF: Limit not (clean)
    - Vokal DIAM: Full power (fill)
    """
    print(f"   🧠 Smart Dynamic Filter: Active={max_poly_active}, Idle={max_poly_idle}...")
    
    vocal_intervals = []
    buffer = 0.2  # Margin keamanan
    for vn in vocal_inst.notes:
        vocal_intervals.append((vn.start - buffer, vn.end + buffer))
        
    playable_notes = [n for n in midi_inst.notes if (n.end - n.start) >= min_duration]
    path_notes = sorted(playable_notes, key=lambda x: x.start)
    final_notes = []
    
    if not path_notes:
        midi_inst.notes = []
        return midi_inst

    current_cluster = [path_notes[0]]
    
    def get_dynamic_limit(cluster_start_time):
        for v_start, v_end in vocal_intervals:
            if v_start <= cluster_start_time <= v_end:
                return max_poly_active 
        return max_poly_idle 

    for i in range(1, len(path_notes)):
        note = path_notes[i]
        prev_note = path_notes[i-1]
        
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            limit = get_dynamic_limit(current_cluster[0].start)
            final_notes.extend(select_best_notes(current_cluster, limit, False))
            current_cluster = [note]
            
    if current_cluster:
        limit = get_dynamic_limit(current_cluster[0].start)
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
    """
    Frequency-Aware Conflict Resolution.
    """
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
            if m_note.start > c_note.start + time_tolerance:
                break 
            
            if abs(c_note.start - m_note.start) <= time_tolerance:
                if abs(c_note.pitch - m_note.pitch) < pitch_safety_gap:
                    should_remove = True
                    break
        
        if should_remove:
            removed_count += 1
        else:
            cleaned_chord_notes.append(c_note)
    
    print(f"      -> Dihapus {removed_count} not yang menabrak frekuensi vokal.")
    chord_inst.notes = cleaned_chord_notes
    return chord_inst

def main():
    parser = argparse.ArgumentParser(description="MIDI Grand Piano Processor (Conditional Double)")
    
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_clean.mid")
    
    # Feature Toggles
    parser.add_argument("--double_vocal", action='store_true', default=True)
    parser.add_argument("--max_poly", type=int, default=3, help="Max not saat vokal NYANYI")
    
    parser.add_argument("--vol_vocal", type=int, default=100)
    parser.add_argument("--vol_instr", type=int, default=85)
    parser.add_argument("--shift_vocal", type=int, default=1)
    parser.add_argument("--shift_instr", type=int, default=-1)
    parser.add_argument("--min_dur", type=float, default=0.1)
    parser.add_argument("--tolerance", type=float, default=0.1)

    args = parser.parse_args()

    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"❌ Error loading MIDI: {e}")
        return

    print("🎹 Processing Grand Piano Effect...")

    # 1. Adjust Basic
    vocal_track = adjust_track(pm_vocal, args.vol_vocal, args.shift_vocal, "Melody")
    instr_track = adjust_track(pm_instr, args.vol_instr, args.shift_instr, "Accompaniment")

    # 2. THICKEN VOCAL (Updated Logic)
    if args.double_vocal:
        vocal_track = thicken_melody(vocal_track)

    # 3. SMART DYNAMIC FILTER
    instr_track = smart_simplify_instrument(
        instr_track, 
        vocal_track,
        max_poly_active=args.max_poly,
        max_poly_idle=10,
        min_duration=args.min_dur
    )

    # 4. SMART CONFLICT
    instr_track = remove_conflicts_smart(vocal_track, instr_track, time_tolerance=args.tolerance, pitch_safety_gap=15)

    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! Output: {args.output}")

if __name__ == "__main__":
    main()

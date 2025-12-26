import argparse
import pretty_midi

def thicken_melody(midi_inst, add_lower_octave=True):
    """
    FITUR BARU: Menebalkan melodi vokal.
    Membuat duplikat not vokal 1 oktaf lebih rendah.
    Ini meniru teknik pianis memainkan melodi dengan jempol & kelingking.
    """
    print("   💪 Menebalkan Vokal (Octave Doubling)...")
    original_notes = list(midi_inst.notes)
    thickened_notes = []

    for note in original_notes:
        # 1. Simpan not asli (Melodi Utama)
        thickened_notes.append(note)

        # 2. Tambahkan not bayangan (Octave Lower)
        if add_lower_octave:
            shadow_pitch = note.pitch - 12
            # Pastikan tidak terlalu rendah (masuk area bass)
            if shadow_pitch >= 48: # Di atas C3
                shadow_note = pretty_midi.Note(
                    velocity=max(40, note.velocity - 15), # Velocity sedikit lebih pelan biar natural
                    pitch=shadow_pitch,
                    start=note.start,
                    end=note.end
                )
                thickened_notes.append(shadow_note)
    
    midi_inst.notes = thickened_notes
    return midi_inst

def select_best_notes(cluster, max_poly, keep_middle):
    # (Fungsi seleksi not sama seperti sebelumnya)
    if len(cluster) <= max_poly:
        return cluster
    
    cluster.sort(key=lambda x: x.pitch)
    selected_notes = []
    indices_taken = set()
    
    # 1. BASS (Wajib)
    if max_poly >= 1:
        selected_notes.append(cluster[0])
        indices_taken.add(0)
    
    # 2. TOP NOTE (Wajib)
    if max_poly >= 2:
        last_idx = len(cluster) - 1
        if last_idx not in indices_taken:
            selected_notes.append(cluster[last_idx])
            indices_taken.add(last_idx)

    # 3. MIDDLE FILLER
    slots_left = max_poly - len(selected_notes)
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

def smart_simplify_instrument(midi_inst, max_poly=2, keep_middle=False, min_duration=0.1):
    # (Fungsi penyederhanaan sama seperti sebelumnya)
    print(f"   🧠 Smart Filter: Max {max_poly} not per chord...")
    playable_notes = [n for n in midi_inst.notes if (n.end - n.start) >= min_duration]
    path_notes = sorted(playable_notes, key=lambda x: x.start)
    final_notes = []
    
    if not path_notes:
        midi_inst.notes = []
        return midi_inst

    current_cluster = [path_notes[0]]
    for i in range(1, len(path_notes)):
        note = path_notes[i]
        prev_note = path_notes[i-1]
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            final_notes.extend(select_best_notes(current_cluster, max_poly, keep_middle))
            current_cluster = [note]
            
    if current_cluster:
        final_notes.extend(select_best_notes(current_cluster, max_poly, keep_middle))

    midi_inst.notes = final_notes
    return midi_inst

def adjust_track(midi_data, velocity, octave_shift, name):
    new_inst = pretty_midi.Instrument(program=0, name=name)
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
    LOGIKA BARU: Frequency-Aware Conflict Resolution.
    Hanya hapus not instrumen jika:
    1. Waktunya tabrakan dengan vokal, DAN
    2. Pitchnya DEKAT dengan vokal.
    
    Jika pitch instrumen JAUH di bawah vokal (Bass), JANGAN dihapus.
    """
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Smart Conflict Resolution (Proteksi Bass, Tol: {time_tolerance}s)...")
    
    removed_count = 0
    for c_note in chord_inst.notes:
        should_remove = False
        
        for m_note in melody_notes:
            if m_note.start > c_note.start + time_tolerance:
                break
            
            # Cek Tabrakan Waktu
            if abs(c_note.start - m_note.start) <= time_tolerance:
                # Cek Tabrakan Frekuensi (Pitch)
                # Jika jarak pitch instrumen ke vokal kurang dari 1 oktaf (12 semitone), HAPUS.
                # Artinya: Bass (jarak > 12) akan SELAMAT.
                if abs(c_note.pitch - m_note.pitch) < pitch_safety_gap:
                    should_remove = True
                    break
        
        if should_remove:
            removed_count += 1
        else:
            cleaned_chord_notes.append(c_note)
    
    print(f"      -> Dihapus {removed_count} not instrumen (Bass tetap aman).")
    chord_inst.notes = cleaned_chord_notes
    return chord_inst

def main():
    parser = argparse.ArgumentParser(description="MIDI Grand Piano Processor")
    
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_clean.mid")
    
    # Feature Toggles
    parser.add_argument("--double_vocal", action='store_true', default=True, help="Aktifkan penebalan vokal (Default: True)")
    
    parser.add_argument("--max_poly", type=int, default=3, help="Rekomendasi naik ke 3 karena Bass sekarang aman")
    parser.add_argument("--vol_vocal", type=int, default=100)
    parser.add_argument("--vol_instr", type=int, default=85) # Naikkan volume instrumen sedikit
    parser.add_argument("--shift_vocal", type=int, default=1)
    parser.add_argument("--shift_instr", type=int, default=-1)
    parser.add_argument("--keep_sustain", action='store_true')
    parser.add_argument("--min_dur", type=float, default=0.1)
    parser.add_argument("--tolerance", type=float, default=0.1)

    args = parser.parse_args()

    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    print("🎹 Processing Grand Piano Effect...")

    # 1. Adjust Basic
    vocal_track = adjust_track(pm_vocal, args.vol_vocal, args.shift_vocal, "Melody")
    instr_track = adjust_track(pm_instr, args.vol_instr, args.shift_instr, "Accompaniment")

    # 2. THICKEN VOCAL (Fitur Baru)
    if args.double_vocal:
        vocal_track = thicken_melody(vocal_track)

    # 3. SMART FILTER
    instr_track = smart_simplify_instrument(
        instr_track, 
        max_poly=args.max_poly, 
        keep_middle=args.keep_sustain, 
        min_duration=args.min_dur
    )

    # 4. SMART CONFLICT (Fitur Baru: Bass Protection)
    # pitch_safety_gap=15 artinya jika jarak nada > 15 semitone (1.2 oktaf), jangan dihapus.
    instr_track = remove_conflicts_smart(vocal_track, instr_track, time_tolerance=args.tolerance, pitch_safety_gap=15)

    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! Output: {args.output}")

if __name__ == "__main__":
    main()

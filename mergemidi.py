import argparse
import pretty_midi

def thicken_melody(midi_inst, add_lower_octave=True):
    """
    FITUR: Menebalkan melodi vokal (Octave Doubling).
    """
    print("   💪 Menebalkan Vokal (Octave Doubling)...")
    original_notes = list(midi_inst.notes)
    thickened_notes = []

    for note in original_notes:
        thickened_notes.append(note)
        if add_lower_octave:
            shadow_pitch = note.pitch - 12
            if shadow_pitch >= 48: 
                shadow_note = pretty_midi.Note(
                    velocity=max(40, note.velocity - 15),
                    pitch=shadow_pitch,
                    start=note.start,
                    end=note.end
                )
                thickened_notes.append(shadow_note)
    
    midi_inst.notes = thickened_notes
    return midi_inst

def select_best_notes(cluster, limit, keep_middle):
    """
    Memilih not terbaik berdasarkan limit yang diberikan.
    """
    # Jika jumlah not di chord kurang dari limit, ambil semua (Full 10 jari jika limit=10)
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
    UPDATE LOGIC: Dynamic Polyphony.
    - Jika Vokal AKTIF: Limit not (max_poly_active) agar tidak berisik.
    - Jika Vokal DIAM: Full power (max_poly_idle = 10) untuk mengisi kekosongan.
    """
    print(f"   🧠 Smart Dynamic Filter: Active={max_poly_active}, Idle={max_poly_idle}...")
    
    # 1. Petakan waktu aktif vokal (dengan buffer sedikit biar transisi halus)
    # Format: (start, end)
    vocal_intervals = []
    buffer = 0.2  # Detik (margin keamanan sebelum/sesudah vokal)
    for vn in vocal_inst.notes:
        vocal_intervals.append((vn.start - buffer, vn.end + buffer))
        
    playable_notes = [n for n in midi_inst.notes if (n.end - n.start) >= min_duration]
    path_notes = sorted(playable_notes, key=lambda x: x.start)
    final_notes = []
    
    if not path_notes:
        midi_inst.notes = []
        return midi_inst

    current_cluster = [path_notes[0]]
    
    # Fungsi helper cek vokal
    def get_dynamic_limit(cluster_start_time):
        # Cek apakah waktu chord ini ada di dalam interval vokal mana saja
        # (Bisa dioptimasi tapi linear search cukup cepat untuk file MIDI standar)
        for v_start, v_end in vocal_intervals:
            if v_start <= cluster_start_time <= v_end:
                return max_poly_active # Vokal sedang nyanyi -> Sederhanakan
        return max_poly_idle # Vokal diam -> Hajar 10 jari

    for i in range(1, len(path_notes)):
        note = path_notes[i]
        prev_note = path_notes[i-1]
        
        # Kelompokkan not yang main barengan (chord)
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            # Proses cluster sebelumnya
            limit = get_dynamic_limit(current_cluster[0].start)
            final_notes.extend(select_best_notes(current_cluster, limit, False)) # keep_middle False biar dinamis
            current_cluster = [note]
            
    if current_cluster:
        limit = get_dynamic_limit(current_cluster[0].start)
        final_notes.extend(select_best_notes(current_cluster, limit, False))

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
    Frequency-Aware Conflict Resolution.
    Hanya hapus not instrumen jika tabrakan WAKTU dan FREKUENSI.
    """
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Smart Conflict Resolution (Proteksi Bass, Tol: {time_tolerance}s)...")
    
    removed_count = 0
    # Optimasi: Gunakan indeks untuk melodi agar tidak loop dari awal terus
    m_idx = 0
    total_melody = len(melody_notes)

    for c_note in chord_inst.notes:
        should_remove = False
        
        # Majukan indeks melodi yang sudah lewat jauh
        while m_idx < total_melody and melody_notes[m_idx].end < c_note.start - time_tolerance:
            m_idx += 1
            
        # Cek tabrakan dengan range melodi yang relevan
        for i in range(m_idx, total_melody):
            m_note = melody_notes[i]
            if m_note.start > c_note.start + time_tolerance:
                break # Melodi selanjutnya belum mulai
            
            # Cek Tabrakan Waktu
            if abs(c_note.start - m_note.start) <= time_tolerance:
                # Cek Tabrakan Frekuensi (Jika terlalu dekat < 12 semitone/1 oktaf)
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
    parser = argparse.ArgumentParser(description="MIDI Grand Piano Processor (Dynamic Fill)")
    
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_clean.mid")
    
    # Feature Toggles
    parser.add_argument("--double_vocal", action='store_true', default=True)
    parser.add_argument("--max_poly", type=int, default=3, help="Max not saat vokal NYANYI")
    # Max not saat vokal DIAM di-hardcode ke 10 di dalam fungsi logic
    
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
        print(f"❌ Error: {e}")
        return

    print("🎹 Processing Grand Piano Effect with Dynamic Fills...")

    # 1. Adjust Basic
    vocal_track = adjust_track(pm_vocal, args.vol_vocal, args.shift_vocal, "Melody")
    instr_track = adjust_track(pm_instr, args.vol_instr, args.shift_instr, "Accompaniment")

    # 2. THICKEN VOCAL
    if args.double_vocal:
        vocal_track = thicken_melody(vocal_track)

    # 3. SMART DYNAMIC FILTER (Perubahan Utama Disini)
    # Kita passing vocal_track ke dalam fungsi ini
    instr_track = smart_simplify_instrument(
        instr_track, 
        vocal_track,           # Pass vokal untuk referensi waktu
        max_poly_active=args.max_poly, # Pakai 2-3 saat vokal ada
        max_poly_idle=10,      # Pakai 10 saat vokal kosong
        min_duration=args.min_dur
    )

    # 4. SMART CONFLICT (Pembersihan Akhir)
    instr_track = remove_conflicts_smart(vocal_track, instr_track, time_tolerance=args.tolerance, pitch_safety_gap=15)

    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! Output: {args.output}")

if __name__ == "__main__":
    main()

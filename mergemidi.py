import argparse
import pretty_midi
import math

def simplify_instrument(midi_inst, max_polyphony=2, min_duration=0.1):
    """
    Menyederhanakan track instrumen agar tidak terlalu ramai.
    1. Menghapus not yang terlalu pendek (noise).
    2. Membatasi jumlah not yang bunyi bersamaan (polyphony),
       dengan memprioritaskan not nada RENDAH (Bass).
    """
    print(f"   📉 Menyederhanakan Instrumen (Max {max_polyphony} not sekaligus, Hapus < {min_duration}s)...")
    
    # 1. Filter Durasi (Hapus not pendek)
    long_notes = [note for note in midi_inst.notes if (note.end - note.start) >= min_duration]
    
    # 2. Grouping Not berdasarkan waktu mulai (untuk mendeteksi Chord)
    # Kita anggap not yang mulai dalam rentang 0.05 detik adalah "bersamaan"
    path_notes = sorted(long_notes, key=lambda x: x.start)
    final_notes = []
    
    if not path_notes:
        midi_inst.notes = []
        return midi_inst

    current_chord = [path_notes[0]]
    
    for i in range(1, len(path_notes)):
        note = path_notes[i]
        prev_note = path_notes[i-1]
        
        # Jika not ini mulai hampir bersamaan dengan not sebelumnya
        if abs(note.start - prev_note.start) < 0.05:
            current_chord.append(note)
        else:
            # Proses chord sebelumnya
            # Urutkan berdasarkan PITCH (Rendah ke Tinggi)
            current_chord.sort(key=lambda x: x.pitch)
            
            # AMBIL HANYA NOT TERENDAH (Bass) sebanyak max_polyphony
            # Sisa not yang tinggi (treble di tangan kiri) dibuang
            kept_notes = current_chord[:max_polyphony]
            final_notes.extend(kept_notes)
            
            # Reset chord baru
            current_chord = [note]
    
    # Jangan lupa proses chord terakhir
    if current_chord:
        current_chord.sort(key=lambda x: x.pitch)
        final_notes.extend(current_chord[:max_polyphony])

    # Update track
    original_count = len(midi_inst.notes)
    final_count = len(final_notes)
    print(f"      -> Dikurangi dari {original_count} menjadi {final_count} not.")
    
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

def remove_conflicts(melody_inst, chord_inst, time_tolerance=0.05):
    # (Fungsi yang sama seperti sebelumnya untuk prioritas vokal)
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Cek tabrakan dengan vokal (Tol: {time_tolerance}s)...")
    
    removed_count = 0
    for c_note in chord_inst.notes:
        is_clashing = False
        for m_note in melody_notes:
            if m_note.start > c_note.start + time_tolerance:
                break
            if abs(c_note.start - m_note.start) <= time_tolerance:
                is_clashing = True
                break
        
        if is_clashing:
            removed_count += 1
        else:
            cleaned_chord_notes.append(c_note)
            
    chord_inst.notes = cleaned_chord_notes
    print(f"      -> Dihapus {removed_count} not instrumen yang menabrak vokal.")
    return chord_inst

def main():
    parser = argparse.ArgumentParser(description="MIDI Merger: Cleaner & Simplifier")
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_clean.mid")
    
    # Config Suara
    parser.add_argument("--vol_vocal", type=int, default=110)
    parser.add_argument("--vol_instr", type=int, default=60) # Default dikecilkan
    parser.add_argument("--shift_vocal", type=int, default=1)
    parser.add_argument("--shift_instr", type=int, default=-1) # Default diturunkan (Bass)
    
    # Config Pembersihan
    parser.add_argument("--max_poly", type=int, default=2, help="Maksimal not instrumen yg bunyi bareng (Default: 2)")
    parser.add_argument("--min_dur", type=float, default=0.1, help="Hapus not instrumen yg lebih pendek dari ini (detik)")
    parser.add_argument("--tolerance", type=float, default=0.1, help="Toleransi tabrakan vokal vs instrumen")

    args = parser.parse_args()

    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"Error: {e}")
        return

    # 1. Proses Dasar
    print("🎹 Menyiapkan Track...")
    vocal_track = adjust_track(pm_vocal, args.vol_vocal, args.shift_vocal, "Melody")
    instr_track = adjust_track(pm_instr, args.vol_instr, args.shift_instr, "Accompaniment")

    # 2. SIMPLIFIKASI INSTRUMEN (Fitur Baru)
    # Ini akan membuang not yang numpuk dan pendek SEBELUM dicek tabrakan dengan vokal
    instr_track = simplify_instrument(instr_track, max_polyphony=args.max_poly, min_duration=args.min_dur)

    # 3. CONFLICT RESOLUTION
    instr_track = remove_conflicts(vocal_track, instr_track, time_tolerance=args.tolerance)

    # 4. Save
    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    final_midi.write(args.output)
    print(f"✅ Selesai! Disimpan ke: {args.output}")

if __name__ == "__main__":
    main()

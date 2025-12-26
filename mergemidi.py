import argparse
import pretty_midi

def select_best_notes(cluster, max_poly, keep_middle):
    """
    Algoritma Pemilihan Not (Greedy):
    Memilih not dari sebuah chord hingga kuota 'max_poly' terpenuhi.
    
    Prioritas:
    1. Bass (Not Terendah) -> Wajib ada.
    2. Top Note (Not Tertinggi) -> Wajib ada (jika poly >= 2).
    3. Middle Notes -> Pengisi slot sisa (prioritas durasi panjang jika keep_middle=True).
    """
    # Jika jumlah not asli <= kuota, ambil semua (tidak perlu filter)
    if len(cluster) <= max_poly:
        return cluster
    
    # Urutkan chord dari nada rendah ke tinggi
    cluster.sort(key=lambda x: x.pitch)
    
    selected_notes = []
    indices_taken = set() # Untuk mencegah duplikasi pengambilan not
    
    # 1. AMBIL BASS (Index 0)
    if max_poly >= 1:
        selected_notes.append(cluster[0])
        indices_taken.add(0)
    
    # 2. AMBIL TOP NOTE (Index Terakhir)
    if max_poly >= 2:
        last_idx = len(cluster) - 1
        # Cek: jangan ambil lagi jika chord cuma 1 not dan sudah diambil di langkah 1
        if last_idx not in indices_taken:
            selected_notes.append(cluster[last_idx])
            indices_taken.add(last_idx)

    # 3. ISI SISA KUOTA DENGAN NOT TENGAH
    slots_left = max_poly - len(selected_notes)
    
    if slots_left > 0:
        # Kumpulkan kandidat not tengah yang belum diambil
        middle_candidates = []
        for i in range(len(cluster)):
            if i not in indices_taken:
                middle_candidates.append(cluster[i])
        
        # Logika Prioritas Tengah
        if keep_middle:
            # Urutkan berdasarkan durasi (yang panjang didahulukan)
            middle_candidates.sort(key=lambda x: x.end - x.start, reverse=True)
        else:
            # Default: Biarkan urutan berdasarkan pitch, atau acak biar natural
            pass 

        # Ambil kandidat sebanyak slot yang tersisa
        fillers = middle_candidates[:slots_left]
        selected_notes.extend(fillers)

    # Kembalikan hasil dengan urutan pitch yang rapi
    selected_notes.sort(key=lambda x: x.pitch)
    return selected_notes

def smart_simplify_instrument(midi_inst, max_poly=2, keep_middle=False, min_duration=0.1):
    """
    Mengelompokkan not yang bunyi bersamaan, lalu memfilternya menggunakan select_best_notes.
    """
    print(f"   🧠 Smart Filter: Max {max_poly} not per chord...")
    
    # Filter noise (not terlalu pendek)
    playable_notes = [n for n in midi_inst.notes if (n.end - n.start) >= min_duration]
    
    # Urutkan berdasarkan waktu mulai
    path_notes = sorted(playable_notes, key=lambda x: x.start)
    final_notes = []
    
    if not path_notes:
        midi_inst.notes = []
        return midi_inst

    current_cluster = [path_notes[0]]
    
    for i in range(1, len(path_notes)):
        note = path_notes[i]
        prev_note = path_notes[i-1]
        
        # Jika not ini mulai hampir bersamaan (toleransi 50ms)
        if abs(note.start - prev_note.start) < 0.05:
            current_cluster.append(note)
        else:
            # Proses cluster sebelumnya
            processed_notes = select_best_notes(current_cluster, max_poly, keep_middle)
            final_notes.extend(processed_notes)
            
            # Reset cluster baru
            current_cluster = [note]
            
    # Proses cluster terakhir yang tersisa
    if current_cluster:
        final_notes.extend(select_best_notes(current_cluster, max_poly, keep_middle))

    print(f"      -> Disederhanakan dari {len(midi_inst.notes)} menjadi {len(final_notes)} not.")
    midi_inst.notes = final_notes
    return midi_inst

def adjust_track(midi_data, velocity, octave_shift, name):
    """
    Mengubah volume (velocity) dan tinggi nada (octave) track.
    """
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
    """
    Menghapus not instrumen yang bertabrakan waktu dengan not vokal.
    """
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Conflict Resolution (Prioritas Vokal, Tol: {time_tolerance}s)...")
    
    removed_count = 0
    for c_note in chord_inst.notes:
        is_clashing = False
        # Cek apakah not instrumen ini menabrak salah satu not vokal
        for m_note in melody_notes:
            # Optimasi: jika vokal sudah lewat jauh, stop loop
            if m_note.start > c_note.start + time_tolerance:
                break
            
            # Cek selisih waktu
            if abs(c_note.start - m_note.start) <= time_tolerance:
                is_clashing = True
                break
        
        if is_clashing:
            removed_count += 1
        else:
            cleaned_chord_notes.append(c_note)
    
    print(f"      -> Dihapus {removed_count} not instrumen yang menabrak vokal.")
    chord_inst.notes = cleaned_chord_notes
    return chord_inst

def main():
    parser = argparse.ArgumentParser(description="MIDI Smart Merger Final (With Max Poly Control)")
    
    # INPUT FILES (Wajib)
    parser.add_argument("--vocal", required=True, help="File MIDI Vokal (Melodi)")
    parser.add_argument("--instr", required=True, help="File MIDI Instrumen (Iringan)")
    
    # OUTPUT FILE (Default Static)
    parser.add_argument("--output", default="final_clean.mid", help="Nama file output (Default: final_clean.mid)")
    
    # SETTING UTAMA
    parser.add_argument("--max_poly", type=int, default=2, help="Jumlah not maksimal yang bunyi bareng (Default: 2)")
    
    # SETTING VOLUME & OKTAF
    parser.add_argument("--vol_vocal", type=int, default=110, help="Volume Vokal (0-127)")
    parser.add_argument("--vol_instr", type=int, default=65, help="Volume Instrumen (0-127)")
    parser.add_argument("--shift_vocal", type=int, default=1, help="Geser Oktaf Vokal (+1)")
    parser.add_argument("--shift_instr", type=int, default=-1, help="Geser Oktaf Instrumen (-1)")
    
    # SETTING LANJUTAN
    parser.add_argument("--keep_sustain", action='store_true', help="Prioritaskan not panjang saat mengisi slot tengah")
    parser.add_argument("--min_dur", type=float, default=0.1, help="Hapus not di bawah durasi ini (detik)")
    parser.add_argument("--tolerance", type=float, default=0.1, help="Toleransi waktu tabrakan vokal vs instrumen")

    args = parser.parse_args()

    # 1. LOAD FILE
    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"❌ Error saat membuka file MIDI: {e}")
        return

    print("🎹 Sedang memproses MIDI...")

    # 2. ADJUST BASIC (Volume & Oktaf)
    vocal_track = adjust_track(pm_vocal, args.vol_vocal, args.shift_vocal, "Melody")
    instr_track = adjust_track(pm_instr, args.vol_instr, args.shift_instr, "Accompaniment")

    # 3. SMART FILTER (Batasi Keramaian sesuai max_poly)
    instr_track = smart_simplify_instrument(
        instr_track, 
        max_poly=args.max_poly, 
        keep_middle=args.keep_sustain, 
        min_duration=args.min_dur
    )

    # 4. CONFLICT RESOLUTION (Hapus instrumen yg nabrak vokal)
    instr_track = remove_conflicts(vocal_track, instr_track, time_tolerance=args.tolerance)

    # 5. GABUNG DAN SIMPAN
    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! File disimpan sebagai: {args.output}")
    print(f"ℹ️  Info: Vokal diutamakan, Iringan dibatasi max {args.max_poly} not per chord.")

if __name__ == "__main__":
    main()

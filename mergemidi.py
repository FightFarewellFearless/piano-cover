import argparse
import pretty_midi
import random

def humanize_track(midi_inst, timing_jitter=0.02, vel_jitter=10):
    """
    FITUR BARU: Membuat permainan terasa seperti manusia (tidak robotik).
    1. Timing Jitter: Menggeser waktu start sedikit (tidak perfectly quantized).
    2. Velocity Jitter: Menambah variasi tekanan jari.
    """
    print(f"   ✨ Humanizing {midi_inst.name} (Timing & Velocity variation)...")
    for note in midi_inst.notes:
        # 1. Geser waktu sedikit (Human Timing)
        # Random offset antara -0.01s sampai +0.01s
        offset = random.uniform(-timing_jitter, timing_jitter)
        new_start = max(0, note.start + offset)
        new_end = max(new_start + 0.1, note.end + offset) # Jaga durasi min
        
        note.start = new_start
        note.end = new_end
        
        # 2. Variasi Tekanan (Human Velocity)
        # Agar tidak semua not dipukul rata (machine gun effect)
        vel_noise = random.randint(-vel_jitter, vel_jitter)
        note.velocity = max(30, min(120, note.velocity + vel_noise))
        
    return midi_inst

def apply_fake_sustain(midi_inst, max_stretch=1.0):
    """
    FITUR BARU: Auto-Legato / Fake Sustain Pedal.
    Masalah piano "kasar" biasanya karena not terlalu pendek (staccato).
    Fungsi ini memperpanjang not instrumen agar menyambung ke not berikutnya
    (seperti menahan pedal sustain).
    """
    print("   🦶 Menerapkan Auto-Sustain (Legato)...")
    
    # Sortir not per pitch agar kita tahu kapan nada yang SAMA dipukul lagi
    notes_by_pitch = {}
    for note in midi_inst.notes:
        if note.pitch not in notes_by_pitch:
            notes_by_pitch[note.pitch] = []
        notes_by_pitch[note.pitch].append(note)

    for pitch in notes_by_pitch:
        pitch_notes = sorted(notes_by_pitch[pitch], key=lambda x: x.start)
        
        for i in range(len(pitch_notes) - 1):
            curr_note = pitch_notes[i]
            next_note = pitch_notes[i+1]
            
            # Hitung jarak kosong (gap)
            gap = next_note.start - curr_note.end
            
            # Jika gap-nya wajar (kurang dari 1 detik), sambung suaranya!
            if 0 < gap < max_stretch:
                # Perpanjang not sekarang sampai not berikutnya mulai
                # (Dikurangi sedikit 0.02s agar tidak overlap parah/muddy)
                curr_note.end = next_note.start - 0.01
                
    # Sortir ulang waktu global
    midi_inst.notes.sort(key=lambda x: x.start)
    return midi_inst

def thicken_melody(midi_inst, add_lower_octave=True):
    print("   💪 Menebalkan Vokal (Conditional Octave Doubling)...")
    
    original_notes = sorted(midi_inst.notes, key=lambda x: x.start)
    thickened_notes = []
    
    if not original_notes:
        return midi_inst

    def process_cluster(cluster):
        should_double = add_lower_octave and (len(cluster) < 3)
        
        for note in cluster:
            thickened_notes.append(note)
            
            if should_double:
                shadow_pitch = note.pitch - 12
                if shadow_pitch >= 45: # Limit A2
                    # Shadow note dibuat jauh lebih lembut agar tidak menabrak vokal utama
                    shadow_vel = max(30, int(note.velocity * 0.7)) 
                    shadow_note = pretty_midi.Note(
                        velocity=shadow_vel,
                        pitch=shadow_pitch,
                        start=note.start,
                        end=note.end
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
            
    if current_cluster:
        process_cluster(current_cluster)
    
    thickened_notes.sort(key=lambda x: x.start)
    midi_inst.notes = thickened_notes
    return midi_inst

def select_best_notes(cluster, limit, keep_middle):
    if len(cluster) <= limit:
        return cluster
    
    cluster.sort(key=lambda x: x.pitch)
    selected_notes = []
    indices_taken = set()
    
    # 1. BASS (Prioritas Utama untuk Fondasi)
    if limit >= 1:
        selected_notes.append(cluster[0])
        indices_taken.add(0)
    
    # 2. TOP NOTE (Melodi)
    if limit >= 2:
        last_idx = len(cluster) - 1
        if last_idx not in indices_taken:
            selected_notes.append(cluster[last_idx])
            indices_taken.add(last_idx)

    # 3. MIDDLE FILLER
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
    print(f"   🧠 Smart Dynamic Filter (Smoothing Activated)...")
    
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

def adjust_track_dynamic(midi_data, target_velocity, octave_shift, name, is_accompaniment=False):
    """
    UPDATE: Mempertahankan dinamika asli (keras pelan), hanya di-scale.
    Sebelumnya semua not diratakan ke satu velocity -> bikin suara kasar/kaku.
    """
    new_inst = pretty_midi.Instrument(program=0, name=name)
    
    if len(midi_data.instruments) > 0:
        source_inst = midi_data.instruments[0]
        
        # Hitung rata-rata velocity asli untuk scaling factor
        velocities = [n.velocity for n in source_inst.notes]
        if not velocities: return new_inst
        avg_original = sum(velocities) / len(velocities)
        if avg_original == 0: avg_original = 60 # prevent division by zero
        
        scale_factor = target_velocity / avg_original

        for note in source_inst.notes:
            shifted_pitch = note.pitch + (octave_shift * 12)
            if 0 <= shifted_pitch <= 127:
                # Scale velocity tapi jaga limit 1-127
                new_vel = int(note.velocity * scale_factor)
                
                # Jika ini accompaniment, batasi max velocity biar gak nabrak vokal
                if is_accompaniment:
                    new_vel = min(new_vel, 95) # Cap di 95 biar gak terlalu keras
                    
                new_vel = max(30, min(127, new_vel)) # Safety clamp
                
                new_note = pretty_midi.Note(
                    velocity=new_vel, 
                    pitch=shifted_pitch, 
                    start=note.start, 
                    end=note.end
                )
                new_inst.notes.append(new_note)
                
    return new_inst

def remove_conflicts_smart(melody_inst, chord_inst, time_tolerance=0.05, pitch_safety_gap=12):
    cleaned_chord_notes = []
    melody_notes = sorted(melody_inst.notes, key=lambda x: x.start)
    print(f"   🔍 Smart Conflict Resolution (Proteksi Bass)...")
    
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
                # Hanya hapus jika pitch-nya dekat
                if abs(c_note.pitch - m_note.pitch) < pitch_safety_gap:
                    should_remove = True
                    break
        
        if not should_remove:
            cleaned_chord_notes.append(c_note)
    
    chord_inst.notes = cleaned_chord_notes
    return chord_inst

def main():
    parser = argparse.ArgumentParser(description="MIDI Fusion: Smooth & Natural")
    
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_smooth.mid")
    
    parser.add_argument("--double_vocal", action='store_true', default=True)
    parser.add_argument("--max_poly", type=int, default=3)
    
    parser.add_argument("--vol_vocal", type=int, default=105) # Vokal lebih menonjol
    parser.add_argument("--vol_instr", type=int, default=80)  # Piano lebih background
    parser.add_argument("--shift_vocal", type=int, default=0)
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

    print("🎹 Processing: Membuat Piano Halus & Natural...")

    # 1. ADJUST BASIC (Dengan Dynamic Scaling, bukan Flat Velocity)
    vocal_track = adjust_track_dynamic(pm_vocal, args.vol_vocal, args.shift_vocal, "Vocal Melody", is_accompaniment=False)
    instr_track = adjust_track_dynamic(pm_instr, args.vol_instr, args.shift_instr, "Piano Accompaniment", is_accompaniment=True)

    # 2. THICKEN VOCAL
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
    instr_track = remove_conflicts_smart(vocal_track, instr_track, time_tolerance=args.tolerance, pitch_safety_gap=12)

    # --- TAHAP POST-PROCESSING (KUNCI KEHALUSAN) ---
    
    # 5. AUTO SUSTAIN (LEGATO)
    # Ini akan menyambung not-not instrumen yang terputus agar mengalun
    instr_track = apply_fake_sustain(instr_track, max_stretch=1.2)
    
    # 6. HUMANIZER
    # Memberikan sedikit ketidaksempurnaan pada waktu dan tekanan agar tidak robotik
    instr_track = humanize_track(instr_track, timing_jitter=0.015, vel_jitter=8)

    # Final Merge
    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.append(vocal_track)
    final_midi.instruments.append(instr_track)
    
    final_midi.write(args.output)
    print(f"✅ SUKSES! Output Halus Tersimpan: {args.output}")

if __name__ == "__main__":
    main()

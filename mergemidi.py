import argparse
import pretty_midi
import random

def enforce_no_overlap(midi_inst):
    """
    Mencegah vokal/instrumen mati mendadak dengan memastikan 
    tidak ada dua not pada pitch yang sama yang tumpang tindih.
    """
    midi_inst.notes.sort(key=lambda x: x.start)
    notes_by_pitch = {}
    cleaned_notes = []
    
    for note in midi_inst.notes:
        if note.pitch not in notes_by_pitch:
            notes_by_pitch[note.pitch] = []
        notes_by_pitch[note.pitch].append(note)
        
    for pitch in notes_by_pitch:
        p_notes = notes_by_pitch[pitch]
        for i in range(len(p_notes) - 1):
            curr = p_notes[i]
            next_n = p_notes[i+1]
            if curr.end > next_n.start:
                # Potong not sebelumnya agar tidak menabrak not berikutnya
                curr.end = max(curr.start + 0.01, next_n.start - 0.001)
            cleaned_notes.append(curr)
        cleaned_notes.append(p_notes[-1])
        
    midi_inst.notes = sorted(cleaned_notes, key=lambda x: x.start)
    return midi_inst

def humanize_track(midi_inst, vel_jitter=8):
    """
    Memberikan variasi velocity agar tidak kaku, 
    tanpa merusak timing (aman untuk AMT).
    """
    for note in midi_inst.notes:
        noise = random.randint(-vel_jitter, vel_jitter)
        note.velocity = max(45, min(115, note.velocity + noise))
    return midi_inst

def apply_smart_sustain(midi_inst, max_gap=0.5):
    """
    Menyambung not yang terputus (pedal simulation) 
    sekaligus mencegah overlap pitch.
    """
    notes_by_pitch = {}
    for note in midi_inst.notes:
        if note.pitch not in notes_by_pitch: notes_by_pitch[note.pitch] = []
        notes_by_pitch[note.pitch].append(note)

    for pitch in notes_by_pitch:
        p_notes = sorted(notes_by_pitch[pitch], key=lambda x: x.start)
        for i in range(len(p_notes) - 1):
            curr = p_notes[i]
            next_n = p_notes[i+1]
            gap = next_n.start - curr.end
            if 0 < gap < max_gap:
                curr.end = next_n.start - 0.005
            elif gap >= max_gap:
                curr.end += 0.05
    
    return enforce_no_overlap(midi_inst)

def thicken_melody(midi_inst, add_lower_octave=True):
    original_notes = sorted(midi_inst.notes, key=lambda x: x.start)
    thickened_notes = []
    if not original_notes: return midi_inst

    def process_cluster(cluster):
        should_double = add_lower_octave and (len(cluster) < 2)
        for note in cluster:
            thickened_notes.append(note)
            if should_double:
                shadow_pitch = note.pitch - 12
                if shadow_pitch >= 40: 
                    shadow_vel = max(30, int(note.velocity * 0.65)) 
                    thickened_notes.append(pretty_midi.Note(
                        velocity=shadow_vel, pitch=shadow_pitch,
                        start=note.start, end=note.end
                    ))

    current_cluster = [original_notes[0]]
    for i in range(1, len(original_notes)):
        if abs(original_notes[i].start - original_notes[i-1].start) < 0.05:
            current_cluster.append(original_notes[i])
        else:
            process_cluster(current_cluster)
            current_cluster = [original_notes[i]]
    if current_cluster: process_cluster(current_cluster)
    
    midi_inst.notes = thickened_notes
    return enforce_no_overlap(midi_inst)

def smart_simplify_instrument(midi_inst, vocal_inst, max_poly=3):
    vocal_intervals = [(n.start, n.end) for n in vocal_inst.notes]
    path_notes = sorted(midi_inst.notes, key=lambda x: x.start)
    if not path_notes: return midi_inst
    
    final_notes = []
    current_cluster = [path_notes[0]]
    
    def select_best(cluster, limit):
        if len(cluster) <= limit: return cluster
        cluster.sort(key=lambda x: x.pitch)
        selected = [cluster[0]] # Bass
        if limit >= 2: selected.append(cluster[-1]) # Top
        if limit > 2:
            rem = cluster[1:-1]
            rem.sort(key=lambda x: x.velocity, reverse=True)
            selected.extend(rem[:limit-2])
        return selected

    def process_cluster_logic(cluster):
        t_s = cluster[0].start
        is_vocal = any(vs <= t_s <= ve for vs, ve in vocal_intervals)
        limit = max_poly if is_vocal else (max_poly + 2)
        final_notes.extend(select_best(cluster, limit))

    for i in range(1, len(path_notes)):
        if abs(path_notes[i].start - path_notes[i-1].start) < 0.05:
            current_cluster.append(path_notes[i])
        else:
            process_cluster_logic(current_cluster)
            current_cluster = [path_notes[i]]
    if current_cluster: process_cluster_logic(current_cluster)
    midi_inst.notes = final_notes
    return midi_inst

def adjust_track_dynamic(midi_data, target_max, name):
    new_inst = pretty_midi.Instrument(program=0, name=name)
    if not midi_data.instruments: return new_inst
    src = midi_data.instruments[0]
    vels = [n.velocity for n in src.notes]
    if not vels: return new_inst
    max_orig = max(vels)
    for note in src.notes:
        ratio = note.velocity / max_orig
        new_vel = max(50, min(120, int(ratio * target_max)))
        if note.end > note.start:
            new_inst.notes.append(pretty_midi.Note(
                velocity=new_vel, pitch=note.pitch, 
                start=note.start, end=note.end
            ))
    return new_inst

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vocal", required=True)
    parser.add_argument("--instr", required=True)
    parser.add_argument("--output", default="final_clean.mid") # Kembali ke default asli
    parser.add_argument("--double_vocal", action='store_true', default=True)
    parser.add_argument("--max_poly", type=int, default=3)
    parser.add_argument("--vol_vocal", type=int, default=115)
    parser.add_argument("--vol_instr", type=int, default=85)
    args = parser.parse_args()

    try:
        pm_vocal = pretty_midi.PrettyMIDI(args.vocal)
        pm_instr = pretty_midi.PrettyMIDI(args.instr)
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Normalisasi & Cleaning
    vocal_track = adjust_track_dynamic(pm_vocal, args.vol_vocal, "Vocal")
    instr_track = adjust_track_dynamic(pm_instr, args.vol_instr, "Piano")

    # Processing Vocal
    if args.double_vocal:
        vocal_track = thicken_melody(vocal_track)
    vocal_track = enforce_no_overlap(vocal_track)

    # Processing Piano
    instr_track = smart_simplify_instrument(instr_track, vocal_track, max_poly=args.max_poly)
    instr_track = apply_smart_sustain(instr_track)
    instr_track = humanize_track(instr_track)

    final_midi = pretty_midi.PrettyMIDI()
    final_midi.instruments.extend([vocal_track, instr_track])
    final_midi.write(args.output)
    print(f"✅ Output disimpan sebagai: {args.output}")

if __name__ == "__main__":
    main()

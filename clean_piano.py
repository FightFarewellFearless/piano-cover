import mido
import sys

def clean_midi_for_piano(input_path, output_path):
    """
    Sanitizes MIDI data from basic-pitch for clean Piano rendering.
    Removes expressive controllers, enforces Program 0, and limits velocity.
    """
    try:
        # Load the original file
        mid = mido.MidiFile(input_path)
        new_mid = mido.MidiFile()
        
        # Preserve the tempo/timing resolution
        new_mid.ticks_per_beat = mid.ticks_per_beat

        print(f"Processing: {input_path}")
        print(f"Track count: {len(mid.tracks)}")

        for track in mid.tracks:
            new_track = mido.MidiTrack()
            new_mid.tracks.append(new_track)
            
            # 1. ENFORCE PIANO INSTRUMENT
            # We insert this at Time=0 to override any initial settings
            # We assume Channel 0 (default) or maintain the track's channel
            new_track.append(mido.Message('program_change', program=0, time=0))

            for msg in track:
                # 2. FILTER PITCH BENDS
                # The primary cause of the "trumpet" formant artifact.
                if msg.type == 'pitchwheel':
                    continue
                
                # 3. FILTER MODULATION WHEEL (Vibrato)
                # Control Change #1 is standard modulation.
                if msg.type == 'control_change' and msg.control == 1:
                    continue

                # 4. FILTER CHANNEL PRESSURE (Aftertouch)
                # Can cause unintended timbre changes.
                if msg.type == 'aftertouch' or msg.type == 'polytouch':
                    continue

                # 5. SANITIZE NOTE EVENTS
                if msg.type == 'note_on':
                    # Fix Velocity: Cap at 95 to prevent harsh/metallic attacks
                    # and potential clipping.
                    if msg.velocity > 95:
                        msg = msg.copy(velocity=95)
                    # Min Velocity: Ensure notes aren't silent
                    if msg.velocity < 20 and msg.velocity > 0:
                        msg = msg.copy(velocity=30)

                # 6. ENFORCE PROGRAM CONSISTENCY
                # If the file tries to change instrument mid-stream, force it back to 0
                if msg.type == 'program_change':
                    msg = msg.copy(program=0)

                new_track.append(msg)

        new_mid.save(output_path)
        print(f"Successfully saved cleaned MIDI to: {output_path}")

    except Exception as e:
        print(f"Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python clean_piano.py <input_vocal.mid> <output_piano.mid>")
    else:
        clean_midi_for_piano(sys.argv[1], sys.argv[2])

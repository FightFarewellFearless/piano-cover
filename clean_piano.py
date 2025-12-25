import mido
import sys

def clean_midi_for_piano(input_path, output_path):
    """
    Sanitizes MIDI data for clean Piano rendering.
    Fixes the 'rushing' bug by accumulating delta times from deleted messages.
    """
    try:
        mid = mido.MidiFile(input_path)
        new_mid = mido.MidiFile()
        
        # Preserve tempo/resolution
        new_mid.ticks_per_beat = mid.ticks_per_beat

        print(f"Processing: {input_path}")

        for track in mid.tracks:
            new_track = mido.MidiTrack()
            new_mid.tracks.append(new_track)
            
            # 1. ENFORCE PIANO: Add Program Change at start
            # We add this at time=0. Subsequent messages will respect their relative timing.
            new_track.append(mido.Message('program_change', program=0, time=0))
            
            # TIME ACCUMULATOR
            # If we delete a message, we must add its 'time' (ticks) to this buffer
            # so the song doesn't speed up.
            time_buffer = 0

            for msg in track:
                # Add current message's wait time to the buffer
                time_buffer += msg.time

                # --- FILTERING LOGIC ---
                
                # 2. FILTER PITCH BENDS
                if msg.type == 'pitchwheel':
                    # Skip message, but keep the time in time_buffer
                    continue
                
                # 3. FILTER MODULATION (CC #1)
                if msg.type == 'control_change' and msg.control == 1:
                    continue

                # 4. FILTER AFTERTOUCH
                if msg.type == 'aftertouch' or msg.type == 'polytouch':
                    continue

                # --- IF WE REACH HERE, WE ARE KEEPING THE MESSAGE ---
                
                # Create a copy so we don't mutate the original object in memory
                new_msg = msg.copy()
                
                # APPLY ACCUMULATED TIME to this message
                new_msg.time = time_buffer
                # Reset buffer since we just used the time
                time_buffer = 0

                # 5. SANITIZE NOTE EVENTS
                if new_msg.type == 'note_on':
                    # Fix Velocity: Cap at 95
                    if new_msg.velocity > 95:
                        new_msg.velocity = 95
                    # Min Velocity: Ensure notes aren't effectively silent
                    if 0 < new_msg.velocity < 20:
                        new_msg.velocity = 30

                # 6. ENFORCE PROGRAM CONSISTENCY
                if new_msg.type == 'program_change':
                    new_msg.program = 0

                new_track.append(new_msg)

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

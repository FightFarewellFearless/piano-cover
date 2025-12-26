import mido
import sys
from pathlib import Path

def clean_midi_for_piano(input_path, output_path):
    """
    Membersihkan data MIDI agar optimal untuk suara Piano.
    Menghapus Pitch Bend, Control Change, Aftertouch, dan menormalisasi Velocity.
    Menggunakan akumulasi delta-time untuk mencegah 'rushing' (tempo lari).
    """
    try:
        # Menggunakan Pathlib untuk handling path file yang lebih aman
        in_file = Path(input_path)
        
        if not in_file.exists():
            raise FileNotFoundError(f"File input tidak ditemukan: {input_path}")

        mid = mido.MidiFile(in_file)
        new_mid = mido.MidiFile()
        
        # Preservasi tempo dan resolusi (ticks per beat)
        new_mid.ticks_per_beat = mid.ticks_per_beat

        print(f"--> Memproses: {in_file.name}")

        for track in mid.tracks:
            new_track = mido.MidiTrack()
            new_mid.tracks.append(new_track)
            
            # 1. ENFORCE PIANO: Memastikan instrumen adalah Acoustic Grand Piano
            # Ditambahkan di awal track (time=0)
            new_track.append(mido.Message('program_change', program=0, time=0))
            
            # TIME ACCUMULATOR
            # Menyimpan waktu (delta time) dari pesan yang dihapus
            time_buffer = 0
            
            # Flag untuk mengecek apakah track ini memiliki note (bukan track tempo/meta)
            has_notes = False

            for msg in track:
                # Tambahkan waktu pesan saat ini ke buffer
                time_buffer += msg.time

                # --- FILTERING LOGIC ---
                
                # Filter pesan yang tidak diinginkan untuk Piano:
                # 1. Pitchwheel (Piano tidak bisa bending)
                # 2. Control Change (Hapus semua CC noise: modulation, breath, volume glitch)
                # 3. Aftertouch/Polytouch (Piano akustik tidak punya aftertouch)
                if msg.type in ['pitchwheel', 'control_change', 'aftertouch', 'polytouch']:
                    continue
                
                # --- KEEPING MESSAGE ---
                
                # Copy pesan agar aman memodifikasi atribut
                new_msg = msg.copy()
                
                # Terapkan akumulasi waktu ke pesan yang dipertahankan
                new_msg.time = time_buffer
                # Reset buffer setelah dipakai
                time_buffer = 0

                # 4. SANITIZE NOTE EVENTS
                if new_msg.type == 'note_on':
                    has_notes = True
                    
                    # LOGIKA VELOCITY (DINAMIKA)
                    # Note Off seringkali adalah Note On dengan velocity 0.
                    # Kita harus memastikan Velocity 0 TIDAK diubah.
                    
                    current_vel = new_msg.velocity
                    
                    if current_vel > 0: # Hanya proses jika ini bukan Note Off
                        # Cap Max Velocity: Agar tidak terlalu memukul (kaku)
                        if current_vel > 100:
                            new_msg.velocity = 100
                        
                        # Min Velocity: Mengangkat note yang terlalu pelan (ghost notes)
                        # Range 1-25 seringkali adalah noise dari audio separator
                        elif current_vel < 25:
                            new_msg.velocity = 45 # Berikan gain yang cukup agar terdengar jelas
                        
                        # Smoothing: Opsional, bisa ditambahkan curve di sini jika perlu

                # 5. ENFORCE PROGRAM CONSISTENCY
                # Jika ada program change di tengah lagu, paksa kembali ke Piano (0)
                if new_msg.type == 'program_change':
                    new_msg.program = 0

                new_track.append(new_msg)

        new_mid.save(output_path)
        print(f"--> Selesai! Disimpan ke: {output_path}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Usage tetap sama sesuai permintaan
    if len(sys.argv) < 3:
        print("Usage: python clean_piano.py <input_vocal.mid> <output_piano.mid>")
    else:
        clean_midi_for_piano(sys.argv[1], sys.argv[2])

import mido
import sys
from pathlib import Path

class MidiProcessor:
    def __init__(self, input_path, output_path):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        
        # --- KONFIGURASI ---
        
        # 1. HAPUS NOISE: Not di bawah durasi ini dianggap 'sampah'
        self.MIN_NOTE_DURATION = 40  # (sekitar not 1/32)
        
        # 2. LEM PEREKAT: Jarak maksimal antar not untuk bisa disambung
        self.MAX_MERGE_GAP = 120 
        
        # 3. GUNTING PEMBATAS (BARU!): 
        # Batas maksimal panjang not hasil gabungan.
        # Jika not sudah sepanjang ini, berhenti menyambung dan buat not baru.
        # 480 ticks biasanya = 1 Ketuk (Quarter Note). 
        # Ubah ke 960 jika ingin batasnya 2 ketuk.
        self.MAX_TOTAL_DURATION = 960 
        
        # 4. VELOCITY (Clamp)
        self.MIN_VELOCITY = 45   # batas bawah (hindari tipis)
        self.MAX_VELOCITY = 90   # batas atas (hindari cempreng)


    def read_notes(self, track):
        """Mengubah event MIDI menjadi object Note absolut"""
        abs_time = 0
        notes = []
        active_notes = {} 

        for msg in track:
            abs_time += msg.time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                if msg.note in active_notes:
                    start_t, vel = active_notes.pop(msg.note)
                    notes.append({'pitch': msg.note, 'start': start_t, 'end': abs_time, 'velocity': vel})
                active_notes[msg.note] = (abs_time, msg.velocity)
                
            elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_t, vel = active_notes.pop(msg.note)
                    notes.append({'pitch': msg.note, 'start': start_t, 'end': abs_time, 'velocity': vel})
        
        return notes

    def process_notes(self, notes):
        if not notes: return []

        # Urutkan not agar pembacaan urut dari awal lagu
        notes.sort(key=lambda x: x['start'])
        
        cleaned_notes = []
        
        if notes:
            # Ambil not pertama sebagai 'kandidat' yang sedang dibangun
            last_note = notes[0]
            
            for i in range(1, len(notes)):
                current_note = notes[i]
                
                # Hitung Jarak (Gap)
                gap = current_note['start'] - last_note['end']
                
                # Hitung Potensi Panjang Baru (Jika digabung)
                potential_new_end = max(last_note['end'], current_note['end'])
                potential_duration = potential_new_end - last_note['start']
                
                # --- SYARAT PENGGABUNGAN ---
                # 1. Nada harus sama
                # 2. Jarak (gap) dekat (bukan not yang berjauhan)
                # 3. Durasi total belum melebihi batas (MAX_TOTAL_DURATION)
                should_merge = (
                    (current_note['pitch'] == last_note['pitch']) and 
                    (0 <= gap <= self.MAX_MERGE_GAP) and
                    (potential_duration <= self.MAX_TOTAL_DURATION)
                )
                
                if should_merge:
                    # GABUNGKAN (Perpanjang not sebelumnya)
                    last_note['end'] = potential_new_end
                    # Ambil velocity terbesar agar dinamis
                    last_note['velocity'] = max(last_note['velocity'], current_note['velocity'])
                    # 'current_note' kita abaikan karena sudah dilebur ke last_note
                else:
                    # JANGAN GABUNG (Simpan not lama, mulai not baru)
                    if self._is_valid(last_note):
                        cleaned_notes.append(last_note)
                    
                    # Jadikan not sekarang sebagai kandidat baru
                    last_note = current_note
            
            # Jangan lupa simpan not terakhir yang tersisa di memori
            if self._is_valid(last_note):
                cleaned_notes.append(last_note)
                
        # Velocity Clamp (lebih musikal, tidak cempreng)
        for note in cleaned_notes:
            note['velocity'] = max(
                self.MIN_VELOCITY,
                min(note['velocity'], self.MAX_VELOCITY)
            )


        return cleaned_notes

    def _is_valid(self, note):
        """Filter not yang terlalu pendek (glitch)"""
        duration = note['end'] - note['start']
        return duration >= self.MIN_NOTE_DURATION

    def write_track(self, notes):
        """Konversi kembali ke MIDI Track"""
        new_track = mido.MidiTrack()
        new_track.append(mido.Message('program_change', program=0, time=0))
        
        events = []
        for note in notes:
            events.append({'time': note['start'], 'type': 'note_on', 'note': note['pitch'], 'velocity': note['velocity']})
            events.append({'time': note['end'], 'type': 'note_off', 'note': note['pitch'], 'velocity': 0})
            
        events.sort(key=lambda x: x['time'])
        
        last_time = 0
        for event in events:
            delta = event['time'] - last_time
            if delta < 0: delta = 0
            
            if event['type'] == 'note_on':
                new_track.append(mido.Message('note_on', note=event['note'], velocity=event['velocity'], time=delta))
            else:
                new_track.append(mido.Message('note_on', note=event['note'], velocity=0, time=delta))
            last_time = event['time']
            
        return new_track

    def run(self):
        try:
            if not self.input_path.exists():
                raise FileNotFoundError(f"File {self.input_path} tidak ditemukan.")
                
            mid = mido.MidiFile(self.input_path)
            new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)
            
            print(f"--> Processing: {self.input_path.name}")
            
            # Auto-scale parameter berdasarkan resolusi MIDI (Ticks Per Beat)
            # Default asumsi 480 ticks/beat
            scale = mid.ticks_per_beat / 480.0
            
            self.MIN_NOTE_DURATION = int(self.MIN_NOTE_DURATION * scale)
            self.MAX_MERGE_GAP = int(self.MAX_MERGE_GAP * scale)
            self.MAX_TOTAL_DURATION = int(self.MAX_TOTAL_DURATION * scale)

            print(f"    Settings (scaled): MinDur={self.MIN_NOTE_DURATION}, MaxGap={self.MAX_MERGE_GAP}, MaxLen={self.MAX_TOTAL_DURATION}")

            for i, track in enumerate(mid.tracks):
                has_notes = any(msg.type == 'note_on' for msg in track)
                
                if has_notes:
                    notes = self.read_notes(track)
                    cleaned_notes = self.process_notes(notes)
                    new_track = self.write_track(cleaned_notes)
                    new_mid.tracks.append(new_track)
                else:
                    # Copy Meta Track (Tempo dll) tapi bersihkan CC
                    clean_meta = mido.MidiTrack()
                    for msg in track:
                        if msg.type not in ['control_change', 'pitchwheel', 'aftertouch']:
                            clean_meta.append(msg)
                    new_mid.tracks.append(clean_meta)

            new_mid.save(self.output_path)
            print(f"--> Selesai: {self.output_path}")
            
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python clean_piano_limit.py <input.mid> <output.mid>")
    else:
        MidiProcessor(sys.argv[1], sys.argv[2]).run()

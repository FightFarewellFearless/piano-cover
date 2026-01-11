import mido
import sys
from pathlib import Path

class MidiProcessor:
    def __init__(self, input_path, output_path):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        
        # --- KONFIGURASI (DIUBAH UNTUK VOKAL LEBIH HALUS) ---
        
        # 1. HAPUS NOISE
        self.MIN_NOTE_DURATION = 60
        
        # 2. LEM PEREKAT (Diperlonggar sedikit agar vokal lebih nyambung)
        self.MAX_MERGE_GAP = 180  # Naik dari 120 ke 180
        
        # 3. BATAS PANJANG NOT
        self.MAX_TOTAL_DURATION = 960 
        
        # 4. VELOCITY (Dibuat lebih lembut/soft)
        self.MIN_VELOCITY = 65   # Naikkan batas bawah (agar vokal jelas/tebal)
        self.MAX_VELOCITY = 85   # Turunkan batas atas (agar tidak kasar/cempreng)
        
        # 5. LEGATO OVERLAP (BARU!)
        # Jumlah ticks not akan diperpanjang menabrak not berikutnya.
        # Ini kuncinya agar suara "ngalun" (tidak putus-putus).
        self.LEGATO_AMOUNT = 40


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

    def _apply_legato(self, notes):
        """
        Membuat not sedikit tumpang tindih (overlap) dengan not berikutnya
        jika jaraknya dekat. Ini menciptakan efek 'Legato' (nyambung).
        """
        if len(notes) < 2:
            return notes
            
        for i in range(len(notes) - 1):
            current_note = notes[i]
            next_note = notes[i+1]
            
            # Hitung jarak antara akhir not sekarang dengan awal not depan
            gap = next_note['start'] - current_note['end']
            
            # Jika jaraknya dekat (kurang dari 1 ketuk/480), kita sambung
            # Tapi jangan sambung jika pitch-nya sama (karena sudah di-merge logic sebelumnya)
            if gap < 480 and current_note['pitch'] != next_note['pitch']:
                # Perpanjang not sekarang sampai not berikutnya mulai + overlap sedikit
                new_end = next_note['start'] + self.LEGATO_AMOUNT
                
                # Pastikan tidak membuat not jadi super panjang (sanity check)
                if new_end - current_note['start'] < self.MAX_TOTAL_DURATION + 200:
                    current_note['end'] = new_end
                    
        return notes

    def process_notes(self, notes):
        if not notes: return []

        # Urutkan not
        notes.sort(key=lambda x: x['start'])
        
        merged_notes = []
        
        if notes:
            # --- TAHAP 1: PENGGABUNGAN NOT SEJENIS (Sama Pitch) ---
            last_note = notes[0]
            
            for i in range(1, len(notes)):
                current_note = notes[i]
                gap = current_note['start'] - last_note['end']
                potential_new_end = max(last_note['end'], current_note['end'])
                potential_duration = potential_new_end - last_note['start']
                
                should_merge = (
                    (current_note['pitch'] == last_note['pitch']) and 
                    (0 <= gap <= self.MAX_MERGE_GAP) and
                    (potential_duration <= self.MAX_TOTAL_DURATION)
                )
                
                if should_merge:
                    last_note['end'] = potential_new_end
                    # Ambil velocity rata-rata agar transisi volume halus (bukan max)
                    last_note['velocity'] = int((last_note['velocity'] + current_note['velocity']) / 2)
                else:
                    if self._is_valid(last_note):
                        merged_notes.append(last_note)
                    last_note = current_note
            
            if self._is_valid(last_note):
                merged_notes.append(last_note)

        # --- TAHAP 2: LEGATO & VELOCITY SMOOTHING ---
        
        # Terapkan Legato (antar not beda pitch)
        final_notes = self._apply_legato(merged_notes)
                
        # Velocity Clamp
        for note in final_notes:
            note['velocity'] = max(
                self.MIN_VELOCITY,
                min(note['velocity'], self.MAX_VELOCITY)
            )

        return final_notes

    def _is_valid(self, note):
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
        
        # Penting: Sort event berdasarkan waktu karena Legato mengubah end time
        # sehingga urutan bisa saja sedikit bergeser (overlap)
        events.sort(key=lambda x: (x['time'], 0 if x['type']=='note_off' else 1))
        
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
            
            print(f"--> Processing Vokal Halus: {self.input_path.name}")
            
            scale = mid.ticks_per_beat / 480.0
            
            # Scale parameter
            self.MIN_NOTE_DURATION = int(self.MIN_NOTE_DURATION * scale)
            self.MAX_MERGE_GAP = int(self.MAX_MERGE_GAP * scale)
            self.MAX_TOTAL_DURATION = int(self.MAX_TOTAL_DURATION * scale)
            self.LEGATO_AMOUNT = int(self.LEGATO_AMOUNT * scale)

            print(f"    Settings: MergeGap={self.MAX_MERGE_GAP}, LegatoOverlap={self.LEGATO_AMOUNT}")

            for i, track in enumerate(mid.tracks):
                has_notes = any(msg.type == 'note_on' for msg in track)
                
                if has_notes:
                    notes = self.read_notes(track)
                    cleaned_notes = self.process_notes(notes)
                    new_track = self.write_track(cleaned_notes)
                    new_mid.tracks.append(new_track)
                else:
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

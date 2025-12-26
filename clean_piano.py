import mido
import sys
from pathlib import Path

class MidiProcessor:
    def __init__(self, input_path, output_path):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        
        # --- KONFIGURASI SMART FILTER ---
        # Ambang batas durasi not (dalam ticks). 
        # Jika ticks_per_beat = 480 (standar), maka 60 ticks itu not 1/32 (sangat pendek).
        self.MIN_NOTE_DURATION = 60  
        
        # Ambang batas gap (jeda) antar not untuk digabung.
        # Jika jarak antar not < 120 ticks, akan disambung jadi 1.
        self.MAX_MERGE_GAP = 120 
        
        # Ambang batas velocity (kekerasan suara).
        self.MIN_VELOCITY = 30
        self.FIXED_VELOCITY = 85 # Velocity standar agar piano terdengar stabil

    def read_notes(self, track):
        """
        Mengubah event MIDI delta-time menjadi daftar objek Note dengan waktu absolut.
        Format: {'note': pitch, 'start': abs_time, 'end': abs_time, 'velocity': vel}
        """
        abs_time = 0
        notes = []
        # Dictionary untuk melacak not yang sedang berbunyi: {pitch: start_time}
        active_notes = {} 

        for msg in track:
            abs_time += msg.time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                # Jika not sudah aktif (overlap), matikan dulu (tekan ulang)
                if msg.note in active_notes:
                    start_t, vel = active_notes.pop(msg.note)
                    notes.append({
                        'pitch': msg.note,
                        'start': start_t,
                        'end': abs_time,
                        'velocity': vel
                    })
                # Mulai not baru
                active_notes[msg.note] = (abs_time, msg.velocity)
                
            elif (msg.type == 'note_off') or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active_notes:
                    start_t, vel = active_notes.pop(msg.note)
                    notes.append({
                        'pitch': msg.note,
                        'start': start_t,
                        'end': abs_time,
                        'velocity': vel
                    })
        
        return notes

    def process_notes(self, notes):
        """
        Inti kecerdasan: Filter noise dan gabungkan not (Merge).
        """
        if not notes:
            return []

        # 1. Urutkan berdasarkan waktu mulai
        notes.sort(key=lambda x: x['start'])
        
        cleaned_notes = []
        
        # BUFFER LOGIC: Kita simpan not terakhir untuk dibandingkan dengan not sekarang
        if notes:
            last_note = notes[0]
            
            for i in range(1, len(notes)):
                current_note = notes[i]
                
                # --- LOGIKA MERGING (Menyambung not putus) ---
                # Syarat: Pitch sama DAN Jarak (gap) antar not dekat
                gap = current_note['start'] - last_note['end']
                
                if (current_note['pitch'] == last_note['pitch']) and (0 <= gap <= self.MAX_MERGE_GAP):
                    # GABUNGKAN: Perpanjang durasi 'last_note' sampai akhir 'current_note'
                    last_note['end'] = max(last_note['end'], current_note['end'])
                    # Ambil velocity terbesar di antara keduanya agar ekspresif
                    last_note['velocity'] = max(last_note['velocity'], current_note['velocity'])
                    # 'current_note' dilewati (dianggap sudah merge ke last_note)
                else:
                    # Jika tidak bisa diming, simpan last_note ke hasil (jika lolos filter)
                    if self._is_valid(last_note):
                        cleaned_notes.append(last_note)
                    last_note = current_note
            
            # Jangan lupa simpan not terakhir
            if self._is_valid(last_note):
                cleaned_notes.append(last_note)
                
        # Normalisasi Velocity (Opsional: agar suara Piano rata/jelas)
        for note in cleaned_notes:
            # Boost velocity kecil, atau set ke fixed
            if note['velocity'] < self.MIN_VELOCITY:
                note['velocity'] = self.FIXED_VELOCITY
            else:
                # Sedikit kompresi agar tidak ada yang terlalu pelan
                note['velocity'] = max(self.FIXED_VELOCITY, note['velocity'])

        return cleaned_notes

    def _is_valid(self, note):
        """Filter Logic: Cek apakah not layak disimpan"""
        duration = note['end'] - note['start']
        # Hapus jika durasi terlalu pendek (noise "salah tekan")
        if duration < self.MIN_NOTE_DURATION:
            return False
        return True

    def write_track(self, notes, original_track):
        """
        Mengubah kembali daftar not absolut menjadi MIDI Track (delta-time).
        """
        new_track = mido.MidiTrack()
        
        # Tambahkan event meta/setup dari track asli (kecuali note events)
        # Kita paksa Program Change ke Piano (0) di awal
        new_track.append(mido.Message('program_change', program=0, time=0))
        
        # Buat daftar event (Note On dan Note Off)
        events = []
        for note in notes:
            events.append({'time': note['start'], 'type': 'note_on', 'note': note['pitch'], 'velocity': note['velocity']})
            events.append({'time': note['end'], 'type': 'note_off', 'note': note['pitch'], 'velocity': 0})
            
        # Urutkan event berdasarkan waktu absolut
        events.sort(key=lambda x: x['time'])
        
        # Konversi ke Delta Time
        last_time = 0
        for event in events:
            delta = event['time'] - last_time
            if delta < 0: delta = 0 # Safety
            
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
            
            print(f"--> Memproses: {self.input_path.name}")
            print(f"--> Ticks Per Beat: {mid.ticks_per_beat}")
            
            # Sesuaikan threshold berdasarkan resolusi MIDI file
            # Kita asumsi setting default diatas untuk 480 tpb. Kita scale jika beda.
            scale_factor = mid.ticks_per_beat / 480.0
            self.MIN_NOTE_DURATION = int(self.MIN_NOTE_DURATION * scale_factor)
            self.MAX_MERGE_GAP = int(self.MAX_MERGE_GAP * scale_factor)

            # Copy Meta Tracks (Tempo, Time Signature) apa adanya
            # Proses Note Tracks
            for i, track in enumerate(mid.tracks):
                # Cek apakah track ini track musik (ada note_on)
                has_notes = any(msg.type == 'note_on' for msg in track)
                
                if has_notes:
                    print(f"    - Optimasi Track {i} (Piano Logic)...")
                    notes = self.read_notes(track)
                    cleaned_notes = self.process_notes(notes)
                    new_track = self.write_track(cleaned_notes, track)
                    new_mid.tracks.append(new_track)
                else:
                    # Jika track tempo/meta, copy saja tapi bersihkan CC
                    print(f"    - Copy Meta Track {i}...")
                    clean_meta_track = mido.MidiTrack()
                    for msg in track:
                        if msg.type not in ['control_change', 'pitchwheel', 'aftertouch']:
                            clean_meta_track.append(msg)
                    new_mid.tracks.append(clean_meta_track)

            new_mid.save(self.output_path)
            print(f"--> Sukses! File bersih disimpan di: {self.output_path}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python clean_piano.py <input.mid> <output.mid>")
    else:
        processor = MidiProcessor(sys.argv[1], sys.argv[2])
        processor.run()

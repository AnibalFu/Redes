class Window:

    def __init__(self):
        self.base = 0
        self.next_seq_num = 0
        self.size = 4
        self.sent_packets = [None] * self.size

    def slide(self):
        if self.base < self.next_seq_num:
            self.base += 1

    def can_send(self) -> bool:
        return self.next_seq_num < self.base + self.size

    def mark_sent(self, datagram):
        if self.can_send():
            self.sent_packets[self.next_seq_num % self.size] = datagram
            self.next_seq_num += 1
            return self.next_seq_num
        
    def mark_received(self, acknum: int):
        if acknum >= self.base:
            self.base = acknum + 1
        print(f"[DEBUG] Ventana movida. Base: {self.base}, Next_seq_num: {self.next_seq_num}")

    def is_at_base(self) -> bool:
        return self.base == self.next_seq_num
        
    def get_packet(self, seq_num: int):
        return self.sent_packets[seq_num % self.size]
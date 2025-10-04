from dataclasses import dataclass
from typing import Optional

from lib.protocolo_amcgf import Datagram

@dataclass
class Window:
    base: int = 0
    next_seq_num: int = 0
    size: int = 4
    sent_packets: list[Optional[Datagram]] | None = None

    def __post_init__(self):
        if self.sent_packets is None:
            self.sent_packets = [None] * self.size

    def slide(self):
        if self.base < self.next_seq_num:
            self.base += 1
    
    def can_send(self) -> bool:
        return self.next_seq_num < self.base + self.size

    def mark_sent(self, datagram: Datagram) -> int | None:
        if self.can_send():
            self.sent_packets[self.next_seq_num % self.size] = datagram
            self.next_seq_num += 1
            return self.next_seq_num
        
    def mark_received(self, acknum: int) -> None:
        if acknum >= self.base:
            self.base = acknum + 1
        self.next_seq_num = self.base

    def is_at_base(self) -> bool:
        return self.base == self.next_seq_num
        
    def get_packet(self, seq_num: int) -> Optional[Datagram]:
        return self.sent_packets[(seq_num - self.base) % self.size]
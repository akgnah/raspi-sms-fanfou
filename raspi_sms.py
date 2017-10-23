# -*- coding: utf-8 -*-
import six
import time
import serial
import fanfou


class Dongle:
    def __init__(self):
        self.ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
        self.write('AT^U2DIAG=0\r')
        self.write('AT+CMGF=1\r')
        self.write('AT+CSDH=1\r')
        self.write('AT+CPMS="ME","ME","ME"\r')

    def write(self, command):
        self.ser.write(command.encode('utf8'))
        self.resp = self.ser.readlines()
        self.resp = [line.decode('utf8') for line in self.resp]

    def cmgl(self, stat):
        self.write('AT+CMGL="%s"\r' % stat)

    def cmgd(self, index):
        self.write('AT+CMGD=%s\r' % index)

    def fetch(self, stat='REC UNREAD'):  # ALL = REC UNREAD + REC READ
        self.cmgl(stat)
        self.out = []
        if 'OK' in self.resp[-1]:
            self.out = list(zip(self.resp[1:-2:2], self.resp[2:-2:2]))
        return self.out

    def close(self):
        self.ser.close()


class Reader:
    def parse(self, head, text):
        head = head.split(',')
        self.index = head[0].split(':')[1].strip()
        self.phone = head[2][-12:-1]  # sometime maybe startwiths +86
        self.time = u'{},{}'.format(head[4], head[5])[1:-1]
        self.size = int(head[-1].strip())
        self.text = self.decode(text[:-2], self.size)

    def decode(self, text, size):
        out = []
        if len(text) == size:  # plain
            out = list(text)
        elif len(text) == 2 * size:  # ascii
            for i in range(0, len(text), 2):
                out.append(six.unichr(int(text[i:i + 2], 16)))
        else:  # unicode
            for i in range(0, len(text), 4):
                out.append(six.unichr(int(text[i:i + 4], 16)))
        return u''.join(out)


if __name__ == '__main__':
    consumer = {'key': 'your key', 'secret': 'your secret'}
    client = fanfou.XAuth(consumer, 'username', 'password')
    fanfou.bound(client)
    phone = '13800138000'  # your phone number

    dongle = Dongle()
    reader = Reader()

    while True:
        for item in dongle.fetch():
            print('reading sms...')
            reader.parse(*item)
            if phone == reader.phone:
                resp = client.statuses.update({'status': reader.text})
                if resp.code == 200:
                    dongle.cmgd(reader.index)
        time.sleep(180)

# -*- coding: utf-8 -*-
import six
import time
import serial
import fanfou


class Dongle:
    def __init__(self):
        self.reader = Reader()
        self.ser = serial.Serial('/dev/ttyUSB3', 115200, timeout=1)
        self.write('AT^U2DIAG=0\r')
        self.write('AT+CMGF=1\r')
        self.write('AT+CSDH=1\r')
        self.write('AT+CSCS="UCS2"\r')
        self.write('AT+CPMS="ME","ME","ME"\r')

    def write(self, command):
        self.ser.write(command.encode('utf8'))
        self.resp = self.ser.readlines()
        self.resp = [line.decode('utf8') for line in self.resp]

    def cmgl(self, stat):
        self.write('AT+CMGL="%s"\r' % stat)

    def cmgd(self, index):
        for _index in index.split(','):
            self.write('AT+CMGD=%s\r' % _index)

    def fetch(self, stat='REC UNREAD'):  # ALL = REC UNREAD + REC READ
        self.cmgl(stat)
        self.out = []
        if 'OK' in self.resp[-1]:
            self.out = self.reader.parse(self.resp)
        return self.out

    def close(self):
        self.ser.close()


class Reader:
    def __init__(self):
        self.buffer = {}

    def storage(self):
        class Storage(dict):
            __getattr__ = dict.get
            __setattr__ = dict.__setitem__
            __delattr__ = dict.__delitem__
        return Storage()

    def parse(self, resp):
        out = []
        for item in zip(resp[1:-2:2], resp[2:-2:2]):
            item = self._parse(*item)
            if item.page > 0:
                last = self.buffer.get(item.phone)
                if last and last.uidx == item.uidx:
                    if last.page < item.page:
                        last.text = last.text + item.text
                    else:
                        last.text = item.text + last.text
                    last.index += ',' + item.index
                    if len(last.index.split(',')) == item.pages:
                        del last.uidx
                        del last.page
                        del last.pages
                        out.append(last)
                        del self.buffer[last.phone]
                    else:
                        self.buffer[item.phone] = last
                else:
                    self.buffer[item.phone] = item
            else:
                del item.page
                out.append(item)
        return out

    def _parse(self, head, text):
        head = head.split(',')
        item = self.storage()
        item.page = 0
        item.index = head[0].split(': ')[1]
        item.phone = head[2][-12:].strip('"')  # sometime maybe startwiths +86
        item.time = u'{} {}'.format(head[3], head[4])[1:-4]
        item.size = int(head[7])
        item.text = self.decode(text[:-2], item.size)
        if len(head) > 8:
            item.uidx = int(head[-3])
            item.page = int(head[-2])
            item.pages = int(head[-1])
        return item

    def decode(self, text, size):
        out = []
        if len(text) == size:  # plain
            out = list(text)
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
    print('reading sms...')

    def update(text, size):
        print('update status...')
        try:
            if size > 140:
                chunks = [text[i:i + 134] for i in range(0, size, 134)]
                for i, v in enumerate(chunks):
                    text = '[%s/%s] %s' % (i + 1, len(chunks), v)
                    client.statuses.update({'status': text})
                    time.sleep(1)
            else:
                client.statuses.update({'status': text})
        except Exception:
            return 'Error'
        return 'OK'

    while True:
        for item in dongle.fetch():
            if phone == item.phone:
                if update(item.text, item.size) == 'OK':
                    dongle.cmgd(item.index)
        time.sleep(180)

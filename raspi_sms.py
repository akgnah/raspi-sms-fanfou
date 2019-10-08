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
        self.data = []
        if 'OK' in self.resp[-1]:
            self.data = self.reader.parse(self.resp)
        return self.data

    def close(self):
        self.ser.close()


class Reader:
    def __init__(self):
        self._uidx = 0

    def gen_uidx(self):
        self._uidx -= 1
        return self._uidx

    def storage(self):
        class Storage(dict):
            __getattr__ = dict.get
            __setattr__ = dict.__setitem__
            __delattr__ = dict.__delitem__
        return Storage()

    def merge(self, item, tmp):
        tmp = list(zip(*sorted(tmp)))
        item.index = ','.join(tmp[1])
        item.text = ''.join(tmp[2])
        item.size = sum(tmp[3])
        del item.page, item.uidx
        return item

    def parse(self, resp):
        buffer = {}
        for item in zip(resp[1:-2:2], resp[2:-1:2]):
            item = self._parse(*item)
            last, tmp = buffer.get(item.uidx) or (item, [])
            tmp.append([item.page, item.index, item.text, item.size])
            buffer[item.uidx] = (last, tmp)
        return [self.merge(*x) for x in buffer.values()]

    def _parse(self, head, text):
        head = head.split(',')
        item = self.storage()
        if len(head) <= 8:
            item.page = 0
            item.uidx = self.gen_uidx()
        else:
            item.page = int(head[-2])
            item.uidx = int(head[-3])
        item.index = head[0].split(': ')[1]
        item.phone = head[2][-12:].strip('"')  # sometime maybe startwiths +86
        item.time = u'{} {}'.format(head[3], head[4])[1:-4]
        item.size = int(head[7])
        item.text = self.decode(text[:-2], item.size)
        return item

    def decode(self, text, size):
        if len(text) == size:  # plain
            tmp = list(text)
        else:  # unicode
            conv = lambda x, i: six.unichr(int(x[i:i + 4], 16))
            tmp = [conv(text, i) for i in range(0, len(text), 4)]
        return u''.join(tmp)


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

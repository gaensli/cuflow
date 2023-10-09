import sys
from PIL import Image, ImageDraw, ImageFont
import math
import cuflow as cu
import svgout
import dip
import eagle
import collections
from dazzler import Dazzler
from collections import defaultdict, namedtuple

from arduino_dazzler import LibraryPart
from EDS import EDS

import shapely.geometry as sg

__VERSION__ = "1.0.1"

def gentext(s):
    fn = "../../.fonts/Arista-Pro-Alternate-Light-trial.ttf"
    fn = "../../.fonts/IBMPlexSans-SemiBold.otf"
    font = ImageFont.truetype(fn, 120)
    im = Image.new("L", (2000, 1000))
    draw = ImageDraw.Draw(im)
    draw.text((200, 200), s, font=font, fill = 255)
    return im.crop(im.getbbox())

I2CBus = namedtuple('I2CBus', ['sda', 'scl'])

# https://cdn-learn.adafruit.com/assets/assets/000/078/438/original/arduino_compatibles_Feather_M4_Page.png
class Feather(dip.dip):
    family = "U"
    width   = cu.inches(.8)
    N       = 32
    N2      = (16, 12)
    def place(self, dc):
        dip.dip.place(self, dc)
        names = "RESET 3V AREF GND A0 A1 A2 A3 A4 A5 SCK MOSI MISO RX TX D4 SDA SCL D5 D6 D9 D10 D11 D12 D13 USB EN BAT"
        for p,nm in zip(self.pads, names.split()):
            p.setname(nm)
        self.s("GND").copy().setname("GL2").thermal(1.3).wire(layer = "GBL")
        self.s("3V").copy().setname("GL3").thermal(1.3).wire(layer = "GTL")
        # pico.s("3V3(OUT)").setname("GL3").thermal(1.3).wire(layer = "GTL")

    def escape(self):
        pp = [p for p in self.pads if p.name not in ("GND", "3V")]
        c = self.board.c
        n = 13
        pivot = pp[n].copy().left(90)  # bottom left pad
        w = pivot.distance(pp[n + 1])

        order = pp[0:14][::-1] + pp[14:][::-1]
        for i,p in enumerate(order):
            dst = pivot.copy().forward((w / 2) - (c * len(order) / 2) + c * i)
            p.goto(dst)
            p.dir = order[0].dir
        r = cu.River(self.board, order)
        return r

    def interface(self, name):
        if name == "analog":
            return "A0"
        return {
            "tx" : "TX",
            "rx" : "RX",
            "sda" : "SDA",
            "scl" : "SCL",
            "sck" : "SCK",
            "mosi" : "MOSI",
            "miso" : "MISO",
            "d5" : "D5",
            "d6" : "D6",
            "d9" : "D9",
            "d10" : "D10",
            "5v" : "BAT",
        }.get(name, name)

class Pico(dip.dip):
    family  = "U"
    width   = 17.78
    N       = 40

    def padfoot(self, p):
        p.stadium(0.8, 60, 1.7)

    def place(self, dc):
        dip.dip.place(self, dc)
        for i in range(40):
            self.pads[i].setname(str(i + 1))

        gpins = {3, 8, 13, 18, 23, 28, 33, 38}
        io = set(range(1, 35)) - gpins
        for g in gpins:
            p = self.s(str(g)).copy()
            p.setname("GL2").thermal(1.3).wire(layer = "GBL")
        pnames = [
            "GP0",
            "GP1",
            "GND",
            "GP2",
            "GP3",
            "GP4",
            "GP5",
            "GND",
            "GP6",
            "GP7",
            "GP8",
            "GP9",
            "GND",
            "GP10",
            "GP11",
            "GP12",
            "GP13",
            "GND",
            "GP14",
            "GP15",
            "GP16",
            "GP17",
            "GND",
            "GP18",
            "GP19",
            "GP20",
            "GP21",
            "GND",
            "GP22",
            "RUN",
            "GP26",
            "GP27",
            "GND",
            "GP28",
            "ADC_VREF",
            "3V3(OUT)",
            "3V3_EN",
            "GND",
            "VSYS",
            "VBUS"
        ]
        for pad,nm in zip(self.pads, pnames):
            pad.right(90)
            pad.copy().w("f 5").text(nm)
            # p = pad.copy().w("l 45 f 2 r 45 f 5 r 45 f 2").wire()
            # dc.board.hole(p.xy, .8)
            # p.n_agon(0.8, 60)
            # p.contact()
            pad.setname(nm)
        self.s("3V3(OUT)").copy().setname("GL3").thermal(1.3).wire(layer = "GTL")
        self.pool = {
            "analog" : ["GP26", "GP27", "GP28"],
            "digital" : ["GP10", "GP11", "GP12", "GP13", "GP14"],
            "tx" : ["GP0", "GP8"],
            "rx" : ["GP1", "GP9"],
        }

    def escape(self):
        pp = [p for p in self.pads if p.name not in ("GND", "3V3(OUT)")]
        c = self.board.c
        n = 15
        pivot = pp[n].copy().left(180)  # bottom left pad
        w = pivot.distance(pp[n + 1])

        order = pp[0:n+1][::-1] + pp[n+1:][::-1]
        for i,p in enumerate(order):
            dst = pivot.copy().forward((w / 2) - (c * len(order) / 2) + c * i)
            p.left(90).goto(dst)
            p.dir = order[0].dir
        r = cu.River(self.board, order)
        return r

    def interface(self, name):
        if name in self.pool:
            return self.pool[name].pop(0)
        return {
            "sda" : "GP14",
            "scl" : "GP15",
            "5v" : "VSYS",
        }.get(name, name)

def addlabels(part):
    for pad in part.pads:
        nm = pad.name
        if nm is not None:
            p = pad.copy().right(90)
            p.copy().w("f 3").text(nm)

class SD(eagle.LibraryPart):
    libraryfile = "x.lbrSD_TF_holder.lbr"
    partname = "MICROSD"
    source = {'LCSC': 'C91145'}
    inBOM = True
    family = "J"

class Distributor(cu.Part):
    family = "J"
    def place(self, dc):
        N = int(self.val)
        brd = self.board
        self.gap = (brd.via / 2) + (brd.via_space) + (brd.trace / 2)
        self.bars = []
        def w():
            self.bars.append(dc.copy().right(90))
            self.pads.append(dc.copy().left(90))
        self.train(dc, N, w, self.gap)
        self.rails = [p.copy().right(180) for p in self.pads]
        self.othernames = ["VH"]

    def escape(self, n):
        return self.board.enriver90(self.pads[::-1][:n], 90)

    def breakout(self, bus):
        for (pa, ra, nm) in zip(self.pads, self.rails, self.othernames + [t.name for t in bus.tt]):
            pa.name = ra.name = nm

        if 1:
            for i,r in enumerate(self.rails):
                r.forward(2 + 6 * (i % 2))
                r.text(str(r.name))

    def via(self, name, conn):
        (r,b) = {r.name:(r,b) for (r,b) in zip(self.rails, self.bars)}[name]
        (sideways, forward) = r.seek(conn)
        r.copy().forward(forward).via().through().right(90).forward(sideways).wire(width = conn.width)

    def finish(self):
        for b in self.bars:
            b.forward(70).wire()

class ArduinoR3(LibraryPart):
    libraryfile = "adafruit.lbr"
    partname = "ARDUINOR3"
    use_pad_text = True
    cut_outline = False
    family = "J"
    inBOM = False
    def escape(self):
        for nm in ("GND", "GND1", "GND2"):
            self.s(nm).setname("GL2").thermal(1.3).wire(layer = "GBL")


class Protoboard:

    def __init__(self):
        self.brd = cu.Board(
            (100, 100),
            trace = 0.127,
            space = 0.127 * 2.0,
            via_hole = 0.3,
            via = 0.6,
            via_space = 0.2,
            silk = cu.mil(6))

        self.upper_edge = 32
        self.lower_edge = 22

    def mcu_feather(self):
        brd = self.brd
        mcu = Feather(brd.DC((16, 73)))
        addlabels(mcu)
        self.common_mcu(mcu, brd.DC((20.6, 38)))

    def mcu_pico(self):
        brd = self.brd
        mcu = Pico(brd.DC((16, 67)))
        self.common_mcu(mcu, brd.DC((21.5, 24)))

    def common_mcu(self, mcu, dp):
        mb = mcu.escape()

        du = Distributor(dp, str(len(mb) + 1))
        md = du.escape(len(mb))
        du.breakout(mb)
        self.mcu = mcu
        self.du = du

        self.du.finish()
        md.wire()
        md.meet(mb)
        mb.wire()

    def finish(self):
        brd = self.brd

        brd.outline()

        for x in (4, 100 - 4):
            for y in (4, 100 - 4):
                brd.hole((x, y), 2.7, 6)

        if 1:
            brd.fill_any("GTL", "GL3")
            brd.fill_any("GBL", "GL2")

    def save(self, name):
        brd = self.brd
        name = "ezbake"
        brd.save(name)
        svgout.write(brd, name + ".svg")

    def add_module(self, mod, *args):
        mod_signals = mod(*((self, ) + args))

        du = self.du
        mcu = self.mcu

        for (nm, p) in mod_signals:
            du.via(mcu.interface(nm), p)

def Module_i2c_pullups_0402(pb):
    brd = pb.brd
    dc = brd.DC((pb.lower_edge + 0, 11)).right(90)
    pb.lower_edge += 4
    r0 = cu.R0402(dc, '4K7')
    dc.forward(2)
    r1 = cu.R0402(dc, '4K7')
    r0.pads[1].setname("GL3").w("o f 1").wire()
    r1.pads[1].setname("GL3").w("o f 1").wire()

    return {"sda": r0.pads[0], "scl": r1.pads[0]}.items()

def Module_EDS(pb):
    brd = pb.brd
    (sda0, scl0) = EDS(brd.DC((pb.lower_edge + 9, 11)).right(90)).escape()
    pb.lower_edge += 20
    [s.w("o f 1 /") for s in (sda0, scl0)]
    return {"sda" : sda0, "scl" : scl0}.items()

class GPS_NEO_6M(cu.Part):
    family = "U"
    def place(self, dc):
        self.chamfered(dc, 27.6, 26.6)
        dc.goxy((26.6/2) + 0.1, -cu.inches(0.2))
        self.train(dc, 5, lambda: self.rpad(dc, 2, 4), cu.inches(0.1))

    def escape(self):
        pp = self.pads
        pp[3].setname("GL2").w("o f 1 -")
        [pp[i].w("o f 1 /") for i in (0, 1, 2, 4)]

def Module_GPS_NEO_6M(pb):
    brd = pb.brd
    m = GPS_NEO_6M(brd.DC((pb.upper_edge + 14, 85)).right(90))
    m.escape()
    pb.upper_edge += 28

    p = m.pads
    return {"digital" : m.pads[0],
            "rx" : m.pads[1],
            "tx" : m.pads[2],
            "5v" : m.pads[4]}.items()

def Module_RYLR896(pb):
    brd = pb.brd
    conn = dip.SIL(brd.DC((pb.upper_edge + 9, 73)).left(90), "6")
    conn.s("1").setname("GL3").thermal(1.3).wire(layer = "GTL")
    conn.s("6").setname("GL2").thermal(1.3).wire(layer = "GBL")
    pb.upper_edge += 18
    return {"tx" : conn.s("3"),
            "rx" : conn.s("4")}.items()

def Module_einks(pb):
    # https://learn.adafruit.com/adafruit-eink-display-breakouts/circuitpython-code-2
    brd = pb.brd
    conn = dip.SIL(brd.DC((pb.upper_edge + 18, 96)).left(90), "13")
    for (i,(p,l)) in enumerate(zip(conn.pads, "VIN 3V3 GND SCK MISO MOSI ECS D/C SRCS SDCS RST BUSY ENA".split())):
        p.copy().right(90).forward(2 + (i & 1)).text(l)
    conn.s("1").setname("GL3").thermal(1.3).wire(layer = "GTL")
    conn.s("3").setname("GL2").thermal(1.3).wire(layer = "GBL")
    pb.upper_edge += 36
    return {"sck"   : conn.s("4"),
            "miso"  : conn.s("5"),
            "mosi"  : conn.s("6"),
            "d9"    : conn.s("7"),
            "d10"   : conn.s("8"),
            "d5"    : conn.s("11"),
            "d6"    : conn.s("12"),
            }.items()


def ldo(p):
    r = cu.SOT223(p)
    p.goxy(-2.3/2, -5.2).w("r 180")
    cu.C0603(p, val = '4.7 uF', source = {'LCSC' : 'C19666'})
    p.forward(2)
    pa = cu.C0603(p, val = '22 uF', source = {'LCSC': 'C159801'}).pads
    pa[0].w("l 90 f 3").wire(width = 0.4)
    pa[1].w("r 90 f 3").wire(width = 0.4)
    return r.escape()

def Module_VIN(pb, sensing = True):
    brd = pb.brd
    x = pb.upper_edge + 5
    pb.upper_edge += 10
    pt = brd.DC((x, 94)).right(180)
    j1 = dip.Screw2(pt)
    j1.s("1").setname("GL2").thermal(1.5).wire(layer = "GBL")
    vin = j1.s("2")

    pt.w("f 14 r 90 f 0.5 l 90")
    L = ldo(pt.copy())
    L[0].copy().goto(vin).wire(width = 0.5)
    L[1].setwidth(0.5).w("o f 1 l 45 f 1 /")

    vinp = vin.copy().w("/ f 1").wire(width = 0.5)
    if not sensing:
        return {"5v" : L[1], "VH" : vinp}.items()

    pt.w("f 7 r 90 f 2 l 90")

    R2 = cu.R0402(pt, '4K7')
    pt.forward(3)
    R1 = cu.R0402(pt, '330')

    R1.pads[1].w("o l 90 f 0.5 -")
    R2.pads[1].w("o").goto(L[0]).wire()
    vsense = R2.pads[0].goto(R1.pads[0]).w("o r 90 f 1 /")
    
    return {"5v" : L[1], "analog" : vsense, "VH" : vinp}.items()

def Module_7SEG_LARGE(pb):
    brd = pb.brd
    width = cu.inches(0.6) + 1
    conn = dip.SIL(brd.DC((pb.upper_edge + width / 2, 96)).left(90), "6")
    conn.s("1").setname("GL2").thermal(1.3).wire(layer = "GBL")
    for p,nm in zip(conn.pads, ["GND", "LAT", "CLK", "SER", "5V", "12V"]):
        p.copy().right(90).forward(2).text(str(nm))

    pb.upper_edge += width
    return (
            ("digital", conn.s("2")),
            ("digital", conn.s("3")),
            ("digital", conn.s("4")),
            ("5v", conn.s("5")),
            ("VH", conn.s("6")),
           )


class CD40109(cu.TSSOP):
    N = 16
    def escape(self, n):
        names = "VCC ENA A E F B ENB VSS ENC C G NC H D END VDD"
        for p,nm in zip(self.pads, names.split()):
            p.setname(nm)
        enables = set("VCC ENA ENB ENC END".split()[:n])
        for s in "VCC ENA ENB ENC END".split():
            if s in enables | {"VCC"}:
                self.s(s).setname("GL3").w("o f 0.5").wire()
            else:
                self.s(s).w("o -")
        self.s("VSS").w("o -")
        self.s("VDD").w("o f 1.25 /")

        ins = [self.s(c) for c in "ABCD"[:n]]
        outs = [self.s(c) for c in "GHEF"[:n]]

        self.s("A").w("i f 1.5 /")
        self.s("B").w("i f 0.7 /")
        self.s("C").w("i f 0.7 /")
        self.s("D").w("i f 1.5 /")
        self.s("E").w("o f 1 r 90")
        self.s("F").w("o f 2 r 90")
        self.s("H").w("o f 2 l 90")
        self.s("G").w("o f 3 l 90")

        cu.extend2(outs)
        [p.forward(3).wire() for p in outs]
        outs_r = self.board.toriver(outs)
        outs_r.forward(2).wire()

        return {
            'ins': ins,
            'outs': outs_r,
            '5v': self.s("VDD"),
        }

def Module_7SEG_LARGE_LS(pb):
    brd = pb.brd
    width = cu.inches(0.6) + 1
    p = brd.DC((pb.upper_edge + width / 2, 96))
    pb.upper_edge += width
    conn = dip.SIL(p.copy().left(90), "6")

    ls = CD40109(p.w("r 180 f 15  r 90 f 2 l 90   l 180"))
    ls_h = ls.escape(3)

    conn.s("1").setname("GL2").thermal(1.3).wire(layer = "GBL")
    for p,nm in zip(conn.pads, ["GND", "LAT", "CLK", "SER", "5V", "12V"]):
        p.copy().right(90).forward(2).text(str(nm))

    do = [conn.s(c) for c in "234"]
    [p.w("r 90 f 3").wire() for p in do]
    do_r = brd.toriver(do)
    do_r.wire()
    do_r.meet(ls_h["outs"])

    conn.s("5").copy().through().goto(ls_h["5v"]).wire()
    return (
            ("digital", ls_h["ins"][0]),
            ("digital", ls_h["ins"][1]),
            ("digital", ls_h["ins"][2]),
            ("5v", conn.s("5")),
            # ("5v", ls_h["5v"]),
            ("VH", conn.s("6")),
           )

def Module_SwitchInput(pb):
    brd = pb.brd
    width = cu.inches(0.2) + 1
    p = brd.DC((pb.upper_edge + width / 2, 96))
    pb.upper_edge += width
    conn = dip.SIL(p.copy().left(90), "2")
    conn.s("1").setname("GL2").thermal(1.3).wire(layer = "GBL")
    return (
            ("digital", conn.s("2")),
    )

def gen():
    brd = cu.Board(
        (100, 100),
        trace = 0.127,
        space = 0.127 * 2.0,
        via_hole = 0.3,
        via = 0.6,
        via_space = 0.2,
        silk = cu.mil(6))
    brd.outline()

    for x in (4, 100 - 4):
        for y in (4, 100 - 4):
            brd.hole((x, y), 2.7, 6)

    shield = ArduinoR3(brd.DC((110, 70)).right(180))
    shield.escape()

    (sda0, scl0) = EDS(brd.DC((26, 15)).right(90)).escape()

    mcu = Feather(brd.DC((16, 73)))
    addlabels(mcu)
    mb = mcu.escape()

    du = Distributor(brd.DC((20.6, 38)))
    md = du.escape()

    # mb.w("f 1 r 90 f 1 l 90").wire()
    md.wire()
    md.meet(mb)
    mb.wire()
    
    du.breakout(mb)

    [s.w("o f 1 /") for s in (sda0, scl0)]

    du.via("SDA", sda0)
    du.via("SCL", scl0)

    for (sig, ardsig) in [
        ("SCK", "D13"),
        ("MISO", "D12"),
        ("MOSI", "D11"),
        ("D4", "D8"),
        ("D5", "D9"),
        ("USB", "5V"),
        ]:
        du.via(sig, shield.s(ardsig))

    if 1:
        brd.fill_any("GTL", "GL3")
        brd.fill_any("GBL", "GL2")

    for i,s in enumerate(["(C) 2022", "EXCAMERA LABS", str(__VERSION__)]):
        brd.annotate(81, 60 - 1.5 * i, s)

    name = "ezbake"
    brd.save(name)
    svgout.write(brd, name + ".svg")

def feather_eink():
    pb = Protoboard()
    if 0:
        pb.mcu_feather()
        pb.add_module(Module_i2c_pullups_0402)
    else:
        pb.mcu_pico()
    for i in range(1):
        pb.add_module(Module_EDS)
    # pb.add_module(Module_VIN)
    pb.add_module(Module_einks)
    # pb.add_module(Module_RYLR896)
    pb.finish()
    pb.save("ezbake")

def coop_monitor():
    pb = Protoboard()
    pb.mcu_pico()
    for i in range(1):
        pb.add_module(Module_EDS)
    pb.add_module(Module_VIN)
    pb.add_module(Module_RYLR896)
    pb.finish()
    pb.save("ezbake")

def large_clock():
    pb = Protoboard()
    pb.mcu_pico()
    pb.add_module(Module_VIN, False)
    pb.add_module(Module_GPS_NEO_6M)
    pb.add_module(Module_7SEG_LARGE_LS)
    pb.add_module(Module_SwitchInput)
    pb.finish()
    pb.save("ezbake")

if __name__ == "__main__":
    large_clock();

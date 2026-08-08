import struct, sys, math, json
from pathlib import Path
FREE=0xFFFFFFFF; END=0xFFFFFFFE; FAT=0xFFFFFFFD; DIF=0xFFFFFFFC

def u16(b,o): return struct.unpack_from('<H',b,o)[0]
def u32(b,o): return struct.unpack_from('<I',b,o)[0]
def u64(b,o): return struct.unpack_from('<Q',b,o)[0]
class CFB:
 def __init__(self,path):
  self.b=Path(path).read_bytes(); h=self.b[:512]
  assert h[:8]==bytes.fromhex('D0CF11E0A1B11AE1')
  self.ss=1<<u16(h,30); self.mss=1<<u16(h,32)
  self.first_dir=u32(h,48); self.cut=u32(h,56); self.first_mfat=u32(h,60); self.nmfat=u32(h,64)
  nfat=u32(h,44); first_difat=u32(h,68); ndifat=u32(h,72)
  difat=[x for x in struct.unpack_from('<109I',h,76) if x not in (FREE,END)]
  sec=first_difat
  for _ in range(ndifat):
   if sec in (END,FREE): break
   d=self.sector(sec); vals=struct.unpack('<%dI'%(self.ss//4),d)
   difat += [x for x in vals[:-1] if x not in (FREE,END)]
   sec=vals[-1]
  fat=[]
  for s in difat[:nfat]: fat.extend(struct.unpack('<%dI'%(self.ss//4),self.sector(s)))
  self.fat=fat
  dirdata=self.chain_bytes(self.first_dir)
  self.entries=[]
  for i in range(0,len(dirdata),128):
   e=dirdata[i:i+128]
   if len(e)<128: break
   nlen=u16(e,64); name=e[:max(0,nlen-2)].decode('utf-16le','ignore') if nlen>=2 else ''
   typ=e[66]; start=u32(e,116); size=u64(e,120)
   self.entries.append((name,typ,start,size))
  root=next((x for x in self.entries if x[1]==5),None)
  self.ministream=self.chain_bytes(root[2])[:root[3]] if root else b''
  mfatdata=self.chain_bytes(self.first_mfat) if self.first_mfat not in (END,FREE) else b''
  self.mfat=list(struct.unpack('<%dI'%(len(mfatdata)//4),mfatdata[:len(mfatdata)//4*4])) if mfatdata else []
 def sector(self,s):
  o=(s+1)*self.ss; return self.b[o:o+self.ss]
 def chain(self,start,fat=None):
  fat=self.fat if fat is None else fat; out=[]; seen=set(); s=start
  while s not in (END,FREE) and s < len(fat) and s not in seen:
   seen.add(s); out.append(s); s=fat[s]
  return out
 def chain_bytes(self,start): return b''.join(self.sector(s) for s in self.chain(start))
 def stream(self,name):
  for n,t,s,z in self.entries:
   if n.lower()==name.lower():
    if z<self.cut and t==2:
     return b''.join(self.ministream[k*self.mss:(k+1)*self.mss] for k in self.chain(s,self.mfat))[:z]
    return self.chain_bytes(s)[:z]
  raise KeyError(name)

def rk(v):
 div100=v&1; isint=v&2
 if isint:
  n=struct.unpack('<i',struct.pack('<I',v & 0xFFFFFFFC))[0] >> 2
  x=float(n)
 else:
  bits=(v & 0xFFFFFFFC) << 32
  x=struct.unpack('<d',struct.pack('<Q',bits))[0]
 return x/100 if div100 else x

def parse_sst(chunks):
 data=b''.join(chunks); pos=0
 if len(data)<8:return []
 total,unique=struct.unpack_from('<II',data,0); pos=8; out=[]
 for _ in range(unique):
  if pos+3>len(data): break
  cch=u16(data,pos); pos+=2; flags=data[pos];pos+=1
  rich= u16(data,pos) if flags&8 else 0; pos +=2 if flags&8 else 0
  ext= u32(data,pos) if flags&4 else 0; pos +=4 if flags&4 else 0
  nbytes=cch*(2 if flags&1 else 1)
  raw=data[pos:pos+nbytes]; pos+=nbytes
  enc='utf-16le' if flags&1 else 'cp1252'
  try:s=raw.decode(enc,'replace')
  except:s=''
  pos += rich*4+ext
  out.append(s)
 return out

def workbook(path):
 w=CFB(path).stream('Workbook')
 records=[]; p=0
 while p+4<=len(w):
  rid,l=struct.unpack_from('<HH',w,p); d=w[p+4:p+4+l]; records.append((p,rid,d)); p+=4+l
 bounds=[]
 for pos,rid,d in records:
  if rid==0x85 and len(d)>=8:
   off=u32(d,0); ln=d[6]; fl=d[7]; raw=d[8:8+ln*(2 if fl&1 else 1)]
   name=raw.decode('utf-16le' if fl&1 else 'cp1252','replace'); bounds.append((name,off))
 sstchunks=[]
 active=False
 for pos,rid,d in records:
  if rid==0xFC: sstchunks=[d]; active=True
  elif active and rid==0x3C: sstchunks.append(d)
  elif active: break
 sst=parse_sst(sstchunks)
 sheets={}
 for i,(name,off) in enumerate(bounds):
  end=bounds[i+1][1] if i+1<len(bounds) else len(w); cells={}; p=off
  while p+4<=end:
   rid,l=struct.unpack_from('<HH',w,p); d=w[p+4:p+4+l]; p+=4+l
   if rid==0x203 and l>=14:
    r,c,xf=struct.unpack_from('<HHH',d,0); cells[(r,c)]=struct.unpack_from('<d',d,6)[0]
   elif rid==0x27E and l>=10:
    r,c,xf=struct.unpack_from('<HHH',d,0); cells[(r,c)]=rk(u32(d,6))
   elif rid==0xBD and l>=6:
    r,fc=struct.unpack_from('<HH',d,0); lc=u16(d,l-2); q=4
    for c in range(fc,lc+1):
     xf=u16(d,q); val=u32(d,q+2); q+=6; cells[(r,c)]=rk(val)
   elif rid==0xFD and l>=10:
    r,c,xf=struct.unpack_from('<HHH',d,0); idx=u32(d,6); cells[(r,c)]=sst[idx] if idx<len(sst) else f'<SST:{idx}>'
   elif rid==0x204 and l>=8:
    r,c,xf,ln=struct.unpack_from('<HHHH',d,0); cells[(r,c)]=d[8:8+ln].decode('cp1252','replace')
   elif rid==0x6 and l>=14:
    r,c,xf=struct.unpack_from('<HHH',d,0); raw=d[6:14]
    if raw[6:8]!=b'\xff\xff': cells[(r,c)]=struct.unpack('<d',raw)[0]
   elif rid==0x0A: break
  sheets[name]=cells
 return sheets

def dump(path):
 sh=workbook(path)
 for name,cells in sh.items():
  print('SHEET',name,'cells',len(cells))
  if not cells: continue
  mr=max(r for r,c in cells); mc=max(c for r,c in cells)
  for r in range(min(mr+1,30)):
   vals=[cells.get((r,c),'') for c in range(min(mc+1,20))]
   if any(x!='' for x in vals): print(r,vals)
if __name__=='__main__': dump(sys.argv[1])

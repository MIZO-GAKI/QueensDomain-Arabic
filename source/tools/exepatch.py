"""Right-to-left letter reveal for FB_AnimRichTextBlock (Queen's Domain 1.01.03, Steam build 13480).

The plugin's StartCharAnim (UCharColorDecorator, rva 0xbba100) maps a global character index to
(run, local index) and starts that character's fade. Arabic lines are stored in visual order (one run per
line), so revealing local index i reads left to right. The patch redirects the index computation into an
unused int3 padding block, where local = count - 1 - local is applied, but only for runs that contain Arabic
letters (U+0600-06FF or presentation forms U+FB50-FEFF). English and other text is unaffected.

Usage: py tools/exepatch.py <original exe> <patched exe>     (writes a new file; never edits in place)
       py tools/exepatch.py --diff <original exe> <out.json>  (writes the byte patch as JSON for the installer)
"""
import sys, json, hashlib, struct
from keystone import Ks, KS_ARCH_X86, KS_MODE_64

ORIG_SHA256 = '8D805CFF01753F9066BF60E4432A02D91533E4741AC0EAF1649B3C1CD17EE9CF'
TEXT_DELTA = 0x1000 - 0x600          # .text: rva - file offset
HOOK_RVA = 0xbba187                  # movsxd rbx,eax ; lea rcx,[rsp+0xa0]
HOOK_ORIG = bytes.fromhex('4863d8' '488d8c24a0000000')
RESUME_RVA = 0xbba192
CAVE_RVA = 0x554240                  # inside a 3535-byte int3 padding block (0x554231..0x555000)

CAVE_ASM = '''
    mov  rcx, qword ptr [rdi + 0x78]
    mov  rcx, qword ptr [rcx]
    test rcx, rcx
    jz   keep
    movsxd rdx, dword ptr [rdi + 0x308]
    movsxd r8,  dword ptr [rdi + 0x30c]
scan:
    cmp  rdx, r8
    jge  keep
    movzx r9d, word ptr [rcx + rdx*2]
    lea  r10d, [r9 - 0x600]
    cmp  r10d, 0x100
    jb   flip
    sub  r9d, 0xfb50
    cmp  r9d, 0x3b0
    jb   flip
    inc  rdx
    jmp  scan
flip:
    not  eax
    add  eax, dword ptr [rdi + 0x328]
keep:
    movsxd rbx, eax
    lea  rcx, [rsp + 0xa0]
    jmp  {resume}
'''


def assemble():
    ks = Ks(KS_ARCH_X86, KS_MODE_64)
    cave, _ = ks.asm(CAVE_ASM.format(resume=hex(RESUME_RVA)), CAVE_RVA)
    hook, _ = ks.asm('jmp %s' % hex(CAVE_RVA), HOOK_RVA)
    hook = bytes(hook) + b'\x90' * (len(HOOK_ORIG) - len(hook))
    return bytes(cave), hook


def patches(data):
    cave, hook = assemble()
    off = lambda rva: rva - TEXT_DELTA
    assert data[off(HOOK_RVA):off(HOOK_RVA) + len(HOOK_ORIG)] == HOOK_ORIG, 'hook site differs'
    assert data[off(CAVE_RVA) - 15:off(CAVE_RVA) + len(cave) + 16] == b'\xcc' * (len(cave) + 31), 'cave not free'
    return [(off(HOOK_RVA), HOOK_ORIG, hook), (off(CAVE_RVA), b'\xcc' * len(cave), cave)]


def main():
    if sys.argv[1] == '--diff':
        src, out = sys.argv[2], sys.argv[3]
    else:
        src, out = sys.argv[1], sys.argv[2]
    data = open(src, 'rb').read()
    if hashlib.sha256(data).hexdigest().upper() != ORIG_SHA256:
        raise SystemExit('unsupported exe (sha256 mismatch)')
    ps = patches(data)
    b = bytearray(data)
    for o, old, new in ps:
        b[o:o + len(new)] = new
    sha = hashlib.sha256(b).hexdigest().upper()
    if sys.argv[1] == '--diff':
        json.dump({'original_sha256': ORIG_SHA256, 'patched_sha256': sha,
                   'patches': [{'offset': o, 'old': old.hex(), 'new': new.hex()} for o, old, new in ps]},
                  open(out, 'w'), indent=1)
    else:
        open(out, 'wb').write(b)
    print('ok', out, sha)


if __name__ == '__main__':
    main()

# -*- mode: python -*-

block_cipher = None


a = Analysis(['ideascube_raspberrypi_installer/__main__.py'],
             pathex=['/home/thiolliere/developpement/ideascube_raspberrypi_installer'],
             binaries=[('/usr/bin/qemu-system-arm', '.'), ('/usr/bin/qemu-img', '.')],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='__main__',
          debug=False,
          strip=False,
          upx=True,
          console=True )

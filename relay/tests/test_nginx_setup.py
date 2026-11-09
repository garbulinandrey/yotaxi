import tempfile
import unittest
from pathlib import Path
import sys
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from configure_nginx import configure, LOCATION

CONFIG='''server {
    listen 2053 ssl;
    listen [::]:2053 ssl;
    server_name vpn.mikhailnet.ru;
    ssl_certificate /etc/letsencrypt/live/vpn.mikhailnet.ru/fullchain.pem;
    location / { proxy_pass http://127.0.0.1:9999; }
}
'''

class SetupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  self.config=self.root/'available';self.config.write_text(CONFIG)
  self.link=self.root/'enabled';self.link.symlink_to(self.config)
  self.limits=self.root/'limits.conf';self.backups=self.root/'backups';self.calls=[]
 def runner(self,args,check):self.calls.append(args)
 def test_adds_route_and_preserves_symlink_and_old_location(self):
  configure(self.link,self.limits,self.backups,self.runner)
  self.assertTrue(self.link.is_symlink())
  self.assertIn(LOCATION,self.config.read_text())
  self.assertIn('proxy_pass http://127.0.0.1:9999;',self.config.read_text())
  self.assertEqual(next(self.backups.iterdir()).read_text(),CONFIG)
  self.assertEqual(self.calls[-1],['systemctl','reload','nginx'])
 def test_invalid_new_config_is_rolled_back(self):
  def run(args,check):
   self.calls.append(args)
   if len(self.calls)==2:raise subprocess.CalledProcessError(1,args)
  with self.assertRaises(subprocess.CalledProcessError):configure(self.link,self.limits,self.backups,run)
  self.assertEqual(self.config.read_text(),CONFIG);self.assertFalse(self.limits.exists())
 def test_443_is_refused_before_changes(self):
  source=CONFIG.replace('listen 2053 ssl;','listen 2053 ssl;\nlisten 443 ssl;');self.config.write_text(source)
  with self.assertRaises(RuntimeError):configure(self.link,self.limits,self.backups,self.runner)
  self.assertEqual(self.config.read_text(),source);self.assertEqual(self.calls,[])
 def test_duplicate_route_and_existing_limits_are_not_overwritten(self):
  self.limits.write_text('user settings')
  with self.assertRaises(RuntimeError):configure(self.link,self.limits,self.backups,self.runner)
  self.assertEqual(self.limits.read_text(),'user settings');self.assertEqual(self.config.read_text(),CONFIG)

if __name__=='__main__':unittest.main()

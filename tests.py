import os
import unittest
import json
import base64

from app import app, db, models
from config import basedir

class TestCase(unittest.TestCase):
  def setUp(self):
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'test.db')
    self.app = app.test_client()
    db.create_all()

  def tearDown(self):
    db.session.remove()
    db.drop_all()

  def test_index(self):
    rv = self.app.get('/')  
    assert 'OK' in rv.data.decode('utf-8')

  def test_get_contact_list_empty_db(self):
    pass

  def test_get_contact_list(self):
    u = models.User()
    u.username = 'will'
    u.password = 'pass'
    db.session.add(u)
    db.session.commit()

    c = models.Contact()
    c.name = 'Jess'
    c.local_id = 123
    c.user_id = u.id
    db.session.add(c)
    db.session.commit()

    rv = self.app.get('/contacts', headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'pass')).replace('\n', '')) })
    assert rv.status_code == 200
    contacts = json.loads(rv.data.decode('utf-8'))['contact_list']
    assert contacts['123'] == 'Jess'

    # Contacts should have been removed from db once pulled.
    assert len(u.contacts.all()) == 0

  def test_upload_contact_list(self):
    u = models.User()
    u.username = 'will'
    u.password = 'pass'
    db.session.add(u)
    db.session.commit()

    contact_list = {'123': 'Jess'}

    rv = self.app.post('/contacts', data=dict(contact_list=json.dumps(contact_list)), headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'pass')).replace('\n', '')) })
    assert rv.status_code == 200

    user = models.User.query.filter_by(username='will').first()
    contacts = models.Contact.query.filter_by(user_id=user.id).all()
    assert len(contacts) == 1
    assert contacts[0].name == 'Jess'

  def test_upload_contact_list_duplicate_contact(self):
    u = models.User()
    u.username = 'will'
    u.password = 'pass'
    db.session.add(u)
    db.session.commit()

    contact_list = {'123': 'Jess', '123': 'Jess'}

    rv = self.app.post('/contacts', data=dict(contact_list=json.dumps(contact_list)), headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'pass')).replace('\n', '')) })
    assert rv.status_code == 200

    user = models.User.query.filter_by(username='will').first()
    contacts = models.Contact.query.filter_by(user_id=user.id).all()
    assert len(contacts) == 1
    assert contacts[0].name == 'Jess'

  def test_post_user_list_invalid_json(self):
    u = models.User()
    u.username = 'will'
    u.password = 'password'
    db.session.add(u)
    db.session.commit()

    invalid_list_json = '[{contact: }]'
    rv = self.app.post('/contacts', data=dict(contact_list=invalid_list_json), headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'password')).replace('\n', ''))})
    assert rv.status_code == 404


  def test_send_msg_no_login(self):
    rv = self.app.post('/send', data=dict(to_local_id=0, message_body="Hello, World!"))
    assert  rv.status_code == 401

  def test_user_sign_up(self):
    rv = self.app.post('/signup', data=dict(username='will', phone='1111111111'))
    assert rv.status_code == 200
    assert 'OK' in rv.data.decode('utf-8')

  def test_user_sign_up_existing_username(self):
    u = models.User()
    u.username = 'will'
    u.password = 'password!!'
    db.session.add(u)
    db.session.commit()

    rv = self.app.post('/signup', data=dict(username=u.username, phone='1111111111'))
    assert rv.status_code == 200
    assert 'Username already taken' in rv.data.decode('utf-8')

  def test_user_generate_password(self):
    u = models.User()
    password = u.generate_password()
    assert type(password) is str
    assert len(password) == 8

  def test_verify_code(self):
    u = models.User()
    u.username = 'will'
    u.password = 'verify_random'
    db.session.add(u)
    db.session.commit()
    rv = self.app.post('/verify', data=dict(username='will', code='verify_random'))
    assert rv.status_code == 200
    assert 'OK' in rv.data.decode('utf-8')

    rv = self.app.post('/verify', data=dict(username='will', code='not'))
    assert rv.status_code == 200
    assert 'INVALID' in rv.data.decode('utf-8')

  def test_set_registration_id(self):
    u = models.User()
    u.username = 'will'
    u.password = 'verify_random'
    db.session.add(u)
    db.session.commit()

    rv = self.app.post('/registration_id', data=dict(registration_id='1234'), headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'verify_random')).replace('\n', '')) })
    assert rv.status_code == 200
    assert 'OK' in rv.data.decode('utf-8')

    new_user = models.User.query.filter_by(username='will').first()
    assert new_user.registration_id == '1234'

    rv = self.app.post('/registration_id', data=dict(registration_id='1234'), headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'verify_random_invalid')).replace('\n', '')) })
    assert rv.status_code == 401

  def test_add_message(self):
    u = models.User()
    u.username = 'will'
    u.password = 'pass'
    db.session.add(u)
    db.session.commit()

    c = models.Contact()
    c.name = 'Jess'
    c.local_id = 123
    c.user_id = u.id
    db.session.add(c)
    db.session.commit()

    data = dict(message_body='hello',local_id=123) # local_id != contact_id

    rv = self.app.post('/message', data=data, headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'pass')).replace('\n', '')) })
    assert rv.status_code == 200

    msg = models.Message.query.first()
    assert msg.body == 'hello'
    assert msg.contact_id == models.Contact.query.filter_by(name='Jess').first().id

    invalid_data = dict(message_body='hello',local_id=0)
    rv = self.app.post('/message', data=invalid_data, headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'pass')).replace('\n', '')) })
    assert rv.status_code == 400

  def test_get_messages(self):
    u = models.User()
    u.username = 'will'
    u.password = 'pass'
    db.session.add(u)
    db.session.commit()

    c = models.Contact()
    c.name = 'Jess'
    c.local_id = 123
    c.user_id = u.id
    db.session.add(c)
    db.session.commit()

    m = models.Message()
    m.body = 'hello'
    m.contact_id = c.id
    db.session.add(m)
    db.session.commit()

    assert len(models.Contact.query.filter_by(local_id=123).first().messages.all()) == 1

    rv = self.app.get('/message', headers={'Authorization': 'Basic %s' % (base64.encodestring('%s:%s' % ('will', 'pass')).replace('\n', '')) })
    messages = json.loads(rv.data.decode('utf-8'))['messages']
    assert rv.status_code == 200
    assert len(messages) == 1
    assert messages[0]['body'] == 'hello'
    assert messages[0]['local_id'] == 123

    # Ensures message was deleted.
    assert len(models.Contact.query.filter_by(local_id=123).first().messages.all()) == 0


if __name__ == '__main__':
  unittest.main()
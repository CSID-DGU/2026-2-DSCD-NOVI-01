from django.contrib.auth import get_user_model
from django.test import Client, TestCase

User = get_user_model()
JSON = 'application/json'
# Vite 프록시를 거친 요청: 호스트가 localhost:5173으로 유지된다 (vite.config.js)
PROXY = {'HTTP_HOST': 'localhost:5173', 'HTTP_ORIGIN': 'http://localhost:5173'}


class CheckNicknameTests(TestCase):
    def test_available_and_taken(self):
        User.objects.create_user('사용중', 'abcd1234')
        self.assertEqual(self.client.get('/api/auth/check-nickname', {'nickname': '새닉네임'}).json(),
                         {'available': True})
        self.assertEqual(self.client.get('/api/auth/check-nickname', {'nickname': '사용중'}).json(),
                         {'available': False})

    def test_invalid_format(self):
        for nickname in ['', '가', '숫자123', '가' * 13]:
            response = self.client.get('/api/auth/check-nickname', {'nickname': nickname})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {'message': '닉네임은 한글·영문 2~12자여야 합니다.'})


class SignupTests(TestCase):
    def post(self, body):
        return self.client.post('/api/auth/signup', body, content_type=JSON)

    def test_signup_logs_in_and_hashes_password(self):
        response = self.post({'nickname': '손석현', 'password': 'abcd1234'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {'nickname': '손석현'})
        user = User.objects.get(nickname='손석현')
        self.assertNotEqual(user.password, 'abcd1234')
        self.assertTrue(user.check_password('abcd1234'))
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))

    def test_errors(self):
        User.objects.create_user('사용중', 'abcd1234')
        cases = [
            ({'nickname': '사용중', 'password': 'abcd1234'}, '이미 사용 중인 닉네임입니다.'),
            ({'nickname': '가', 'password': 'abcd1234'}, '닉네임은 한글·영문 2~12자여야 합니다.'),
            ({'nickname': '새닉네임', 'password': 'abcdefgh'}, '비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.'),
            ({'nickname': '새닉네임', 'password': 'abc123'}, '비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.'),
            ({'nickname': '새닉네임'}, '닉네임과 비밀번호를 입력해 주세요.'),
            ({'nickname': 1, 'password': 2}, '닉네임과 비밀번호를 입력해 주세요.'),
            ([], '닉네임과 비밀번호를 입력해 주세요.'),
        ]
        for body, message in cases:
            response = self.post(body)
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json(), {'message': message})
        self.assertFalse(User.objects.filter(nickname='새닉네임').exists())

    def test_broken_json(self):
        self.assertEqual(self.post('{').status_code, 400)


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')

    def post(self, body):
        return self.client.post('/api/auth/login', body, content_type=JSON)

    def test_login(self):
        response = self.post({'nickname': '손석현', 'password': 'abcd1234'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'nickname': '손석현'})
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.pk))

    def test_wrong_credentials(self):
        for body in [{'nickname': '손석현', 'password': 'wrong1234'}, {'nickname': '없는사람', 'password': 'abcd1234'}, {}]:
            response = self.post(body)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {'message': '닉네임 또는 비밀번호가 맞지 않아요.'})
        self.assertNotIn('_auth_user_id', self.client.session)


class LogoutAndMeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('손석현', 'abcd1234')
        self.client.force_login(self.user)

    def test_me(self):
        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'nickname': '손석현', 'date_joined': self.user.date_joined.date().isoformat()})

    def test_me_joined_before_the_column_existed(self):
        User.objects.filter(pk=self.user.pk).update(date_joined=None)
        self.assertIsNone(self.client.get('/api/auth/me').json()['date_joined'])

    def test_logout_ends_session(self):
        self.assertEqual(self.client.post('/api/auth/logout').status_code, 204)
        response = self.client.get('/api/auth/me')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {'message': '로그인이 필요합니다.'})


class CsrfTests(TestCase):
    """프론트처럼 CSRF 검사를 켠 채로 요청한다."""

    def setUp(self):
        User.objects.create_user('손석현', 'abcd1234')
        self.client = Client(enforce_csrf_checks=True)
        self.body = {'nickname': '손석현', 'password': 'abcd1234'}

    def test_post_without_token_is_rejected(self):
        response = self.client.post('/api/auth/login', self.body, content_type=JSON, **PROXY)
        self.assertEqual(response.status_code, 403)

    def test_login_with_token_through_proxy(self):
        response = self.client.get('/api/auth/csrf', **PROXY)
        self.assertEqual(response.status_code, 204)
        token = self.client.cookies['csrftoken'].value
        response = self.client.post('/api/auth/login', self.body, content_type=JSON,
                                    HTTP_X_CSRFTOKEN=token, **PROXY)
        self.assertEqual(response.status_code, 200)

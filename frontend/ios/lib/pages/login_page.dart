// Login page — W32 port. Supports email OR username login (account-based).
//
// Mirrors frontend/web/src/views/Login.vue W32 schema:
//   - Tabs: 密码登录 / 手机验证码 (kept for legacy)
//   - 密码登录 uses {account, password} — account = email OR username
//   - SMS 登录 kept as legacy fallback (phone + sms_code)

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../l10n/generated/app_localizations.dart';
import '../main.dart';
import '../services/auth_service.dart';

final _googleSignIn = GoogleSignIn(scopes: ['email', 'profile']);

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> with SingleTickerProviderStateMixin {
  late final TabController _tabController =
      TabController(length: 2, vsync: this);

  final _accountCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _smsCtrl = TextEditingController();

  String _countryCode = '+86';
  bool _agreement = false;
  bool _remember = true;
  bool _submitting = false;

  String? _accountErr;
  String? _pwdErr;
  String? _phoneErr;
  String? _smsErr;
  String? _generalErr;

  @override
  void dispose() {
    _tabController.dispose();
    _accountCtrl.dispose();
    _pwdCtrl.dispose();
    _phoneCtrl.dispose();
    _smsCtrl.dispose();
    super.dispose();
  }

  bool _validateAccount(AppLocalizations l) {
    setState(() {
      _accountErr = null;
      _pwdErr = null;
    });
    final acc = _accountCtrl.text.trim();
    final pwd = _pwdCtrl.text;
    if (acc.isEmpty || (acc.length < 5 && !acc.contains('@'))) {
      _accountErr = '请输入邮箱或用户名';
      return false;
    }
    if (pwd.length < 8) {
      _pwdErr = l.errorsPwdTooShort;
      return false;
    }
    return true;
  }

  bool _validateSms(AppLocalizations l) {
    setState(() {
      _phoneErr = null;
      _smsErr = null;
    });
    final phone = _phoneCtrl.text.trim();
    final code = _smsCtrl.text.trim();
    if (phone.length < 5) {
      _phoneErr = l.errorsPhoneInvalid;
      return false;
    }
    if (!RegExp(r'^\d{6}$').hasMatch(code)) {
      _smsErr = l.errorsCodeInvalid;
      return false;
    }
    return true;
  }

  Future<void> _onAccountSubmit(AppLocalizations l) async {
    if (!_agreement) {
      setState(() => _generalErr = '⚠ ' + l.loginAgreementPrefix);
      return;
    }
    if (!_validateAccount(l)) return;
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final svc = AuthService();
      final result = await svc.loginByAccount(
        account: _accountCtrl.text.trim(),
        password: _pwdCtrl.text,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('欢迎回来, ${result.user.nickname.isNotEmpty ? result.user.nickname : result.user.username}')),
      );
      Navigator.of(context).pushNamedAndRemoveUntil(
        AppRoutes.home,
        (route) => false,
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _onGoogleSignIn(AppLocalizations l) async {
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final account = await _googleSignIn.signIn();
      if (account == null) {
        setState(() => _submitting = false);
        return;
      }
      final auth = await account.authentication;
      final idToken = auth.idToken;
      if (idToken == null) throw Exception('Google ID token missing');
      final svc = AuthService();
      final result = await svc.loginWithGoogle(idToken);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('欢迎, ${result.user.nickname.isNotEmpty ? result.user.nickname : result.user.email}')),
      );
      Navigator.of(context).pushNamedAndRemoveUntil(AppRoutes.home, (route) => false);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _onSmsSubmit(AppLocalizations l) async {
    if (!_agreement) {
      setState(() => _generalErr = '⚠ ' + l.loginAgreementPrefix);
      return;
    }
    if (!_validateSms(l)) return;
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final svc = AuthService();
      await svc.loginBySms(
        phone: _phoneCtrl.text.trim(),
        phoneCountry: _countryCode,
        code: _smsCtrl.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l.toastLoginSuccess)),
      );
      Navigator.of(context).pushNamedAndRemoveUntil(
        AppRoutes.home,
        (route) => false,
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _generalErr = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l.appName), centerTitle: true),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                elevation: 2,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(l.loginTitle,
                          style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
                          textAlign: TextAlign.center),
                      const SizedBox(height: 6),
                      Text(l.loginSubtitle,
                          style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                          textAlign: TextAlign.center),
                      const SizedBox(height: 18),
                      TabBar(
                        controller: _tabController,
                        labelColor: theme.colorScheme.primary,
                        unselectedLabelColor: theme.colorScheme.onSurfaceVariant,
                        indicatorColor: theme.colorScheme.primary,
                        tabs: const [Tab(text: '账号登录'), Tab(text: '手机验证')],
                      ),
                      const SizedBox(height: 18),
                      SizedBox(
                        height: 320,
                        child: TabBarView(
                          controller: _tabController,
                          children: [_buildAccountForm(l, theme), _buildSmsForm(l, theme)],
                        ),
                      ),
                      if (_generalErr != null) ...[
                        const SizedBox(height: 8),
                        Text(_generalErr!,
                            style: TextStyle(color: theme.colorScheme.error, fontSize: 12),
                            textAlign: TextAlign.center),
                      ],
                      const SizedBox(height: 8),
                      Row(children: [
                        Checkbox(value: _agreement, onChanged: (v) => setState(() => _agreement = v ?? false)),
                        Expanded(child: Wrap(children: [
                          Text(l.loginAgreementPrefix + ' '),
                          Text(l.loginAgreementTerms, style: TextStyle(color: theme.colorScheme.primary)),
                          Text(' ' + l.loginAgreementAnd + ' '),
                          Text(l.loginAgreementPrivacy, style: TextStyle(color: theme.colorScheme.primary)),
                        ])),
                      ]),
                      const SizedBox(height: 12),
                      Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        Text(l.loginNoAccount, style: const TextStyle(fontSize: 13, color: Color(0xFF64748B))),
                        TextButton(onPressed: () => Navigator.of(context).pushNamed(AppRoutes.register), child: Text(l.loginGoSignup)),
                      ]),
                      const SizedBox(height: 8),
                      Row(children: [
                        Expanded(child: Divider(color: theme.colorScheme.outlineVariant)),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          child: Text('或', style: TextStyle(fontSize: 12, color: theme.colorScheme.onSurfaceVariant)),
                        ),
                        Expanded(child: Divider(color: theme.colorScheme.outlineVariant)),
                      ]),
                      const SizedBox(height: 8),
                      OutlinedButton.icon(
                        onPressed: _submitting ? null : () => _onGoogleSignIn(l),
                        icon: Image.network(
                          'https://www.google.com/favicon.ico',
                          width: 18,
                          height: 18,
                          errorBuilder: (_, __, ___) => const Icon(Icons.language, size: 18),
                        ),
                        label: const Text('Google 账号登录'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          minimumSize: const Size.fromHeight(44),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAccountForm(AppLocalizations l, ThemeData theme) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      TextField(
        controller: _accountCtrl,
        keyboardType: TextInputType.emailAddress,
        decoration: InputDecoration(
          labelText: '邮箱或用户名',
          hintText: 'user@example.com 或 username',
          errorText: _accountErr,
          prefixIcon: const Icon(Icons.person_outline),
          border: const OutlineInputBorder(),
        ),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _pwdCtrl,
        obscureText: true,
        decoration: InputDecoration(
          labelText: l.loginPwdLabel,
          hintText: l.loginPwdPlaceholder,
          errorText: _pwdErr,
          prefixIcon: const Icon(Icons.lock_outline),
          border: const OutlineInputBorder(),
        ),
      ),
      const SizedBox(height: 8),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Row(mainAxisSize: MainAxisSize.min, children: [
          Checkbox(value: _remember, onChanged: (v) => setState(() => _remember = v ?? false)),
          Text(l.loginRemember, style: const TextStyle(fontSize: 12)),
        ]),
        TextButton(onPressed: () => Navigator.of(context).pushNamed(AppRoutes.forgot), child: Text(l.loginForgot)),
      ]),
      const SizedBox(height: 12),
      FilledButton(
        onPressed: _submitting ? null : () => _onAccountSubmit(l),
        style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
        child: _submitting
            ? SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: theme.colorScheme.onPrimary))
            : const Text('登录'),
      ),
    ]);
  }

  Widget _buildSmsForm(AppLocalizations l, ThemeData theme) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _phoneField(l, theme),
      const SizedBox(height: 12),
      TextField(
        controller: _smsCtrl,
        keyboardType: TextInputType.number,
        maxLength: 6,
        decoration: InputDecoration(
          labelText: l.loginSmsLabel,
          hintText: l.loginSmsPlaceholder,
          errorText: _smsErr,
          counterText: '',
          border: const OutlineInputBorder(),
        ),
      ),
      const SizedBox(height: 8),
      OutlinedButton(
        onPressed: _submitting ? null : () {},
        style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 10)),
        child: Text(l.loginSendCode),
      ),
      const SizedBox(height: 12),
      FilledButton(
        onPressed: _submitting ? null : () => _onSmsSubmit(l),
        style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
        child: _submitting
            ? SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: theme.colorScheme.onPrimary))
            : Text(l.loginSubmit),
      ),
    ]);
  }

  Widget _phoneField(AppLocalizations l, ThemeData theme) {
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(border: Border.all(color: theme.colorScheme.outline), borderRadius: BorderRadius.circular(4)),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            value: _countryCode,
            isDense: true,
            items: const [
              DropdownMenuItem(value: '+86', child: Text('+86 🇨🇳')),
              DropdownMenuItem(value: '+62', child: Text('+62 🇮🇩')),
              DropdownMenuItem(value: '+84', child: Text('+84 🇻🇳')),
              DropdownMenuItem(value: '+63', child: Text('+63 🇵🇭')),
            ],
            onChanged: (v) => setState(() => _countryCode = v ?? '+86'),
          ),
        ),
      ),
      const SizedBox(width: 8),
      Expanded(
        child: TextField(
          controller: _phoneCtrl,
          keyboardType: TextInputType.phone,
          decoration: InputDecoration(
            labelText: l.loginPhoneLabel,
            hintText: l.loginPhonePlaceholder,
            errorText: _phoneErr,
            border: const OutlineInputBorder(),
          ),
        ),
      ),
    ]);
  }
}
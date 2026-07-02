// Register page — W32 port. Schema: username + email + password (no SMS).
//
// Mirrors frontend/web/src/views/Register.vue W32:
//   - username (3-32 chars, [A-Za-z0-9_.-])
//   - email
//   - password (8-32 chars, letters + digits)
//   - confirm password + live strength meter
//   - nickname (optional)
//   - agreement checkbox
//   - submit → POST /api/v2/auth/register → login → home

import 'package:flutter/material.dart';

import '../l10n/generated/app_localizations.dart';
import '../main.dart';
import '../services/auth_service.dart';

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _usernameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _nicknameCtrl = TextEditingController();
  final _pwdCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  bool _agreed = false;
  bool _submitting = false;

  String? _usernameErr;
  String? _emailErr;
  String? _pwdErr;
  String? _confirmErr;
  String? _generalErr;

  static final RegExp _usernameRe = RegExp(r'^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$');
  static final RegExp _emailRe = RegExp(r'^[\w.+\-]+@[\w\-]+(\.[\w\-]+)+$');
  static final RegExp _pwdRe = RegExp(r'^(?=.*[A-Za-z])(?=.*\d)[\w!@#$%^&*()+\-=\[\]{};|\\,.<>/?`~]{8,32}$');

  @override
  void initState() {
    super.initState();
    _pwdCtrl.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _usernameCtrl.dispose();
    _emailCtrl.dispose();
    _nicknameCtrl.dispose();
    _pwdCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  int _pwdStrength() {
    final v = _pwdCtrl.text;
    if (v.isEmpty) return 0;
    if (v.length < 8 || v.length > 32) return 1;
    int score = 0;
    if (RegExp('[A-Za-z]').hasMatch(v)) score++;
    if (RegExp(r'\d').hasMatch(v)) score++;
    if (RegExp(r'[!@#$%^&*()_+\-=\[\]{}|\\,.<>/?`~]').hasMatch(v)) score++;
    if (v.length >= 12) score++;
    if (score >= 3) return 3;
    if (score >= 2) return 2;
    return 1;
  }

  String _pwdStrengthLabel() {
    switch (_pwdStrength()) {
      case 1: return '弱';
      case 2: return '中';
      case 3: return '强';
      default: return '';
    }
  }

  Color _pwdStrengthColor() {
    switch (_pwdStrength()) {
      case 1: return const Color(0xFFDC2626);
      case 2: return const Color(0xFFD97706);
      case 3: return const Color(0xFF16A34A);
      default: return const Color(0xFFCBD5E1);
    }
  }

  bool _validateAll() {
    setState(() {
      _usernameErr = null;
      _emailErr = null;
      _pwdErr = null;
      _confirmErr = null;
    });
    var ok = true;
    if (!_usernameRe.hasMatch(_usernameCtrl.text)) {
      _usernameErr = '3-32 字符,字母数字开头,可含 _.-';
      ok = false;
    }
    if (!_emailRe.hasMatch(_emailCtrl.text.trim())) {
      _emailErr = '邮箱格式不正确';
      ok = false;
    }
    if (!_pwdRe.hasMatch(_pwdCtrl.text)) {
      _pwdErr = '8-32 字符,需含字母和数字';
      ok = false;
    }
    if (_pwdCtrl.text != _confirmCtrl.text) {
      _confirmErr = '两次密码不一致';
      ok = false;
    }
    if (!_agreed) {
      _generalErr = '请先同意条款';
      ok = false;
    }
    return ok;
  }

  Future<void> _onSubmit() async {
    if (!_validateAll()) return;
    setState(() {
      _submitting = true;
      _generalErr = null;
    });
    try {
      final svc = AuthService();
      await svc.register(
        username: _usernameCtrl.text.trim(),
        email: _emailCtrl.text.trim(),
        password: _pwdCtrl.text,
        nickname: _nicknameCtrl.text.trim().isEmpty ? null : _nicknameCtrl.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('注册成功!已自动登录')),
      );
      Navigator.of(context).pushNamedAndRemoveUntil(AppRoutes.home, (_) => false);
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

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: Text(l.navRegister),
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => Navigator.of(context).pop()),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card(
                elevation: 1,
                color: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
                    Text(l.registerTitle,
                        style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
                        textAlign: TextAlign.center),
                    const SizedBox(height: 4),
                    Text(l.registerSubtitle,
                        style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                        textAlign: TextAlign.center),
                    const SizedBox(height: 18),
                    _input('用户名', _usernameCtrl, hint: '3-32 字符,字母数字开头', icon: Icons.person_outline, error: _usernameErr),
                    const SizedBox(height: 12),
                    _input('邮箱', _emailCtrl, hint: 'user@example.com', icon: Icons.email_outlined, error: _emailErr, keyboardType: TextInputType.emailAddress),
                    const SizedBox(height: 12),
                    _input('昵称 (选填)', _nicknameCtrl, hint: '想让别人叫你什么', icon: Icons.tag_outlined),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _pwdCtrl,
                      obscureText: true,
                      maxLength: 32,
                      decoration: InputDecoration(
                        labelText: l.registerPwdLabel,
                        hintText: l.registerPwdPlaceholder,
                        errorText: _pwdErr,
                        prefixIcon: const Icon(Icons.lock_outline),
                        counterText: '',
                        border: const OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    if (_pwdCtrl.text.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      _strengthMeter(),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: _confirmCtrl,
                      obscureText: true,
                      maxLength: 32,
                      decoration: InputDecoration(
                        labelText: l.registerConfirmLabel,
                        errorText: _confirmErr,
                        prefixIcon: const Icon(Icons.lock_outline),
                        counterText: '',
                        border: const OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: 12),
                    _agreement(l),
                    if (_generalErr != null) ...[
                      const SizedBox(height: 6),
                      Text(_generalErr!, style: TextStyle(color: theme.colorScheme.error, fontSize: 12), textAlign: TextAlign.center),
                    ],
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: _submitting ? null : _onSubmit,
                      style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                      child: _submitting
                          ? SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: theme.colorScheme.onPrimary))
                          : Text(l.registerSubmit, style: const TextStyle(fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(height: 16),
                    Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Text(l.registerHaveAccount, style: const TextStyle(fontSize: 13, color: Color(0xFF64748B))),
                      TextButton(onPressed: _submitting ? null : () => Navigator.of(context).pushReplacementNamed(AppRoutes.login), child: Text(l.registerGoLogin)),
                    ]),
                  ]),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _input(String label, TextEditingController ctrl, {String? hint, IconData? icon, String? error, TextInputType? keyboardType}) {
    return TextField(
      controller: ctrl,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        errorText: error,
        prefixIcon: icon != null ? Icon(icon) : null,
        border: const OutlineInputBorder(),
        isDense: true,
      ),
    );
  }

  Widget _strengthMeter() {
    final s = _pwdStrength();
    return Row(children: [
      for (var i = 1; i <= 3; i++)
        Expanded(
          child: Container(
            height: 4,
            margin: EdgeInsets.only(right: i == 3 ? 8 : 4),
            decoration: BoxDecoration(
              color: s >= i ? _pwdStrengthColor() : const Color(0xFFE2E8F0),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
      SizedBox(width: 30, child: Text(_pwdStrengthLabel(), style: TextStyle(fontSize: 11, color: _pwdStrengthColor(), fontWeight: FontWeight.w600))),
    ]);
  }

  Widget _agreement(AppLocalizations l) {
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Checkbox(
        value: _agreed,
        onChanged: (v) => setState(() => _agreed = v ?? false),
        visualDensity: VisualDensity.compact,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
      Expanded(
        child: Padding(
          padding: const EdgeInsets.only(top: 12),
          child: Wrap(children: [
            Text(l.registerAgreementPrefix + ' ', style: const TextStyle(fontSize: 12, color: Color(0xFF475569))),
            Text(l.registerAgreementTerms, style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.primary, decoration: TextDecoration.underline)),
            Text(' ' + l.registerAgreementAnd + ' ', style: const TextStyle(fontSize: 12, color: Color(0xFF475569))),
            Text(l.registerAgreementPrivacy, style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.primary, decoration: TextDecoration.underline)),
          ]),
        ),
      ),
    ]);
  }
}
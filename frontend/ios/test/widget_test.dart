// Widget tests for the W6-4 / W8-1 iOS app — verifies all 3 ported pages
// (home / register / materials) mount successfully and render their key UI
// elements, including the live password strength meter on RegisterPage and
// the MaterialUploader widget on MaterialsPage.
//
// These tests run under `flutter test` (the standard flutter widget test
// harness, no device required). They exercise the real `VisaIosApp` entry
// from lib/main.dart with explicit `initialRoute` + `locale` overrides so
// we don't depend on the default zh fallback.
//
// References:
// - lib/pages/home_page.dart (HomePage, 4 feature cards, 6 country chips)
// - lib/pages/register_page.dart (6 fields: phone + SMS + pwd + confirm +
//   agreement + submit; live strength meter weak/medium/strong)
// - lib/pages/materials_page.dart (3 tabs + MaterialUploader widget)
// - lib/widgets/material_uploader.dart (drag/tap/progress/done)
// - lib/l10n/app_en.arb (en locale copy used in tests for stability)

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:visa_ios/main.dart';

void main() {
  // -----------------------------------------------------------------------
  // Test 1 — HomePage renders slogan + 4 feature cards + 6 country chips
  // (W6-4 iOS multi-page port, page 1/3).
  // -----------------------------------------------------------------------
  testWidgets('home_page renders slogan, 4 feature cards and 6 country chips',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const VisaIosApp(),
    );
    // Default route is '/' (HomePage) and default locale is zh — pump a few
    // frames so the localized copy loads before assertions.
    await tester.pumpAndSettle(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 100));

    // (a) Slogan text — zh default locale copy (locked W6-4 zh ARB).
    expect(
      find.text('签证,其实很简单'),
      findsOneWidget,
      reason: 'HomePage slogan should render the zh ARB homeSlogan copy.',
    );

    // (b) Subtitle text — must mention denial insurance.
    expect(
      find.textContaining('拒签险'),
      findsWidgets,
      reason: 'HomePage subtitle should mention denial insurance feature.',
    );

    // (c) CTA buttons — "立即登录" + "查看支持国家".
    expect(find.text('立即登录'), findsWidgets);
    expect(find.text('查看支持国家'), findsOneWidget);

    // (d) Feature section header.
    expect(find.text('为什么选我们'), findsOneWidget);

    // (e) 4 feature titles — locked W6-4 zh copy.
    expect(find.text('材料清单自动生成'), findsOneWidget);
    expect(find.text('拒签险保障'), findsOneWidget);
    expect(find.text('模板库'), findsOneWidget);
    expect(find.text('Affiliate 计划'), findsOneWidget);

    // (f) 6 country chip names (TH/VN/ID/PH/MY/SG).
    expect(find.text('Thailand'), findsOneWidget);
    expect(find.text('Vietnam'), findsOneWidget);
    expect(find.text('Indonesia'), findsOneWidget);
    expect(find.text('Philippines'), findsOneWidget);
    expect(find.text('Malaysia'), findsOneWidget);
    expect(find.text('Singapore'), findsOneWidget);

    // (g) Brand mark "V" is present.
    expect(find.text('V'), findsOneWidget);
  });

  // -----------------------------------------------------------------------
  // Test 2 — RegisterPage renders 6 fields + live password strength meter
  // (W6-4 iOS multi-page port, page 2/3). Drives the strength meter
  // through weak → medium → strong with three input values.
  // -----------------------------------------------------------------------
  testWidgets(
      'register_page renders 6 fields, agreement checkbox, submit button, '
      'and live password strength meter cycles weak→medium→strong',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const VisaIosApp(),
    );
    await tester.pumpAndSettle(const Duration(milliseconds: 300));

    // Navigate from '/' (Home) to '/register' via the named route table.
    final NavigatorState navigator = tester.state<NavigatorState>(
      find.byType(Navigator).first,
    );
    navigator.pushNamed(AppRoutes.register);
    await tester.pumpAndSettle(const Duration(milliseconds: 300));

    // (a) Page title from zh ARB registerTitle.
    expect(find.text('创建账号'), findsOneWidget);

    // (b) 4 input fields — Phone / SMS / Password / Confirm.
    expect(find.text('手机号'), findsOneWidget);
    expect(find.text('短信验证码'), findsOneWidget);
    expect(find.text('设置密码'), findsOneWidget);
    expect(find.text('确认密码'), findsOneWidget);

    // (c) Send code button + submit button.
    expect(find.text('发送验证码'), findsOneWidget);
    expect(find.text('注册'), findsWidgets);

    // (d) Country code dropdown shows default +86 flag.
    expect(find.text('+86 🇨🇳'), findsOneWidget);

    // (e) Agreement checkbox + terms/privacy text.
    expect(find.byType(Checkbox), findsOneWidget);
    expect(find.text('《用户协议》'), findsOneWidget);
    expect(find.text('《隐私政策》'), findsOneWidget);

    // (f) Drive password strength: weak → medium → strong.
    final pwdFields = find.byType(TextField);
    expect(pwdFields, findsAtLeastNWidgets(4));

    // 1. weak: only 5 chars (below min length).
    await tester.enterText(
        find.widgetWithText(TextField, '设置密码'), 'abc12');
    await tester.pump();
    expect(find.text('弱'), findsOneWidget,
        reason: '5-char password should show Weak (弱) strength label.');

    // 2. medium: 10 chars, letter + digit only.
    await tester.enterText(
        find.widgetWithText(TextField, '设置密码'), 'abcdef1234');
    await tester.pump();
    expect(find.text('中'), findsOneWidget,
        reason: '10-char letter+digit password should show Medium (中) strength.');

    // 3. strong: 12+ chars, letter + digit + symbol.
    await tester.enterText(
        find.widgetWithText(TextField, '设置密码'), 'Abcdef12345!@');
    await tester.pump();
    expect(find.text('强'), findsOneWidget,
        reason: '12+ char mixed password should show Strong (强) strength.');
  });

  // -----------------------------------------------------------------------
  // Test 3 — MaterialsPage renders 3 tabs + MaterialUploader (idle phase)
  // and shows the demo seed item in the collected list (W6-4 iOS multi-page
  // port, page 3/3).
  // -----------------------------------------------------------------------
  testWidgets(
      'materials_page renders 3 tabs, MaterialUploader idle widget, and '
      'demo seed item in collected list',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const VisaIosApp(),
    );
    await tester.pumpAndSettle(const Duration(milliseconds: 300));

    // Navigate '/' → '/materials'.
    final NavigatorState navigator = tester.state<NavigatorState>(
      find.byType(Navigator).first,
    );
    navigator.pushNamed(AppRoutes.materials);
    await tester.pumpAndSettle(const Duration(milliseconds: 300));

    // (a) Page title.
    expect(find.text('材料采集'), findsOneWidget);

    // (b) Subtitle text from zh ARB materialsSubtitle.
    expect(find.textContaining('上传护照'), findsOneWidget);

    // (c) 3 tab labels — Photo / Upload File / Voice.
    expect(find.text('拍照'), findsOneWidget);
    expect(find.text('上传文件'), findsOneWidget);
    expect(find.text('录音'), findsOneWidget);

    // (d) Default tab is photo — MaterialUploader is NOT visible (photo panel
    //     shows a 'W2' notice). Tap the Upload File tab to expose it.
    await tester.tap(find.text('上传文件'));
    await tester.pumpAndSettle(const Duration(milliseconds: 300));

    // (e) MaterialUploader idle phase title + description visible.
    expect(find.text('点击或拖拽上传'), findsOneWidget);
    expect(find.textContaining('PDF / JPG / PNG / WebP'), findsOneWidget);
    expect(find.textContaining('最大 10MB'), findsWidgets);

    // (f) Demo seed item from initState — passport_E1234567.jpg.
    expect(find.text('passport_E1234567.jpg'), findsOneWidget);
    expect(find.textContaining('护照'), findsWidgets);

    // (g) Collected count shows (1).
    expect(find.textContaining('(1)'), findsOneWidget);

    // (h) Validate button present.
    expect(find.text('校验材料'), findsOneWidget);
  });
}

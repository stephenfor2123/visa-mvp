// Agreement page — W13 Flutter iOS port of miniprogram/pages/agreement/.
//
// Two tabs: Terms of Service / Privacy Policy.
// Static content with 4 sections per tab.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';

class AgreementPage extends StatefulWidget {
  const AgreementPage({super.key});

  @override
  State<AgreementPage> createState() => _AgreementPageState();
}

class _AgreementPageState extends State<AgreementPage> with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  String _activeTab = 'terms';

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
    _tabCtrl.addListener(() {
      final tab = _tabCtrl.index == 0 ? 'terms' : 'privacy';
      if (_activeTab != tab) setState(() => _activeTab = tab);
    });
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(icon: const Icon(Icons.arrow_back, color: Color(0xFF1A1A2E)), onPressed: () => Navigator.pop(context)),
        title: Text(l.agreementPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
        bottom: TabBar(
          controller: _tabCtrl,
          labelColor: const Color(0xFF3B6EF5),
          unselectedLabelColor: const Color(0xFF6B7280),
          indicatorColor: const Color(0xFF3B6EF5),
          indicatorWeight: 2,
          tabs: [
            Tab(text: l.agreementTabTerms),
            Tab(text: l.agreementTabPrivacy),
          ],
        ),
      ),
      body: SafeArea(
        child: TabBarView(
          controller: _tabCtrl,
          children: [
            _TermsContent(l: l),
            _PrivacyContent(l: l),
          ],
        ),
      ),
    );
  }
}

class _TermsContent extends StatelessWidget {
  final AppLocalizations l;
  const _TermsContent({required this.l});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(l.agreementTermsTitle, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF1A1A2E))),
        const SizedBox(height: 4),
        Text(l.agreementTermsEffective, style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
        const SizedBox(height: 20),
        _section(l.agreementTermsSection1Title, l.agreementTermsSection1Body),
        _section(l.agreementTermsSection2Title, l.agreementTermsSection2Body),
        _section(l.agreementTermsSection3Title, l.agreementTermsSection3Body),
        _section(l.agreementTermsSection4Title, l.agreementTermsSection4Body),
      ],
    );
  }

  Widget _section(String title, String body) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
          const SizedBox(height: 6),
          Text(body, style: const TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF4B5563))),
        ],
      ),
    );
  }
}

class _PrivacyContent extends StatelessWidget {
  final AppLocalizations l;
  const _PrivacyContent({required this.l});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(l.agreementPrivacyTitle, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF1A1A2E))),
        const SizedBox(height: 4),
        Text(l.agreementPrivacyEffective, style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
        const SizedBox(height: 20),
        _section(l.agreementPrivacySection1Title, l.agreementPrivacySection1Body),
        _section(l.agreementPrivacySection2Title, l.agreementPrivacySection2Body),
        _section(l.agreementPrivacySection3Title, l.agreementPrivacySection3Body),
        _section(l.agreementPrivacySection4Title, l.agreementPrivacySection4Body),
      ],
    );
  }

  Widget _section(String title, String body) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
          const SizedBox(height: 6),
          Text(body, style: const TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF4B5563))),
        ],
      ),
    );
  }
}
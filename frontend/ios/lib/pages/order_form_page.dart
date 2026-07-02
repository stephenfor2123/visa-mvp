// OrderForm page — W14 Flutter iOS port of web/src/views/OrderNew.vue.
//
// Multi-section visa application form with tabs: Basic / Travel / Emergency.
// Auto-fills from materials OCR data (mocked). 4-language support.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class OrderFormPage extends StatefulWidget {
  final String? orderNo;
  OrderFormPage({super.key, String? orderNo})
      : orderNo = orderNo ?? Uri.base.queryParameters['order_no'];

  @override
  State<OrderFormPage> createState() => _OrderFormPageState();
}

class _OrderFormPageState extends State<OrderFormPage> with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  String _activeTab = 'basic';
  bool _loading = false;

  final _tabs = ['basic', 'travel', 'emergency'];

  // Form fields — Basic tab
  final _surnameCtrl = TextEditingController(text: 'SANTOSO');
  final _givenCtrl = TextEditingController(text: 'Budi');
  final _dobCtrl = TextEditingController(text: '1990-01-15');
  final _nationalityCtrl = TextEditingController(text: 'Indonesia');
  final _passportNoCtrl = TextEditingController(text: 'B12345678');
  final _passportExpCtrl = TextEditingController(text: '2030-01-15');

  // Travel tab
  final _arrivalCtrl = TextEditingController(text: '2026-07-01');
  final _departureCtrl = TextEditingController(text: '2026-07-15');
  final _purposeCtrl = TextEditingController(text: 'Tourism');

  // Emergency tab
  final _emergencyNameCtrl = TextEditingController();
  final _emergencyPhoneCtrl = TextEditingController();
  final _emergencyRelCtrl = TextEditingController();

  Map<String, String> _errors = {};

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    _tabCtrl.addListener(() {
      final idx = _tabCtrl.index;
      setState(() => _activeTab = _tabs[idx]);
    });
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    _surnameCtrl.dispose();
    _givenCtrl.dispose();
    _dobCtrl.dispose();
    _nationalityCtrl.dispose();
    _passportNoCtrl.dispose();
    _passportExpCtrl.dispose();
    _arrivalCtrl.dispose();
    _departureCtrl.dispose();
    _purposeCtrl.dispose();
    _emergencyNameCtrl.dispose();
    _emergencyPhoneCtrl.dispose();
    _emergencyRelCtrl.dispose();
    super.dispose();
  }

  void _validate() {
    final errors = <String, String>{};
    if (_surnameCtrl.text.trim().isEmpty) errors['surname'] = 'Required';
    if (_givenCtrl.text.trim().isEmpty) errors['given'] = 'Required';
    if (_passportNoCtrl.text.trim().isEmpty) errors['passportNo'] = 'Required';
    setState(() => _errors = errors);
  }

  void _onSubmit() {
    _validate();
    if (_errors.isNotEmpty) return;
    setState(() => _loading = true);
    // Mock submit
    Future.delayed(const Duration(seconds: 1), () {
      if (!mounted) return;
      setState(() => _loading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Application submitted (mock)'), backgroundColor: Colors.green),
      );
      Navigator.pushNamedAndRemoveUntil(context, AppRoutes.orders, (r) => false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF1A1A2E)),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(l.ordernewPageTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Hero
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              color: Colors.white,
              child: Row(
                children: [
                  const Text('🇮🇩', style: TextStyle(fontSize: 28)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${l.ordernewDestLabel} · ${l.orderItemVisaTourism}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
                        Text('⚡ ${l.ordernewOcrPrefilled}', style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
                      ],
                    ),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Text('< ${l.ordernewBtnBack}', style: const TextStyle(color: Color(0xFF3B6EF5), fontSize: 13)),
                  ),
                ],
              ),
            ),
            // Tabs
            Container(
              color: Colors.white,
              child: TabBar(
                controller: _tabCtrl,
                labelColor: const Color(0xFF3B6EF5),
                unselectedLabelColor: const Color(0xFF6B7280),
                indicatorColor: const Color(0xFF3B6EF5),
                indicatorWeight: 2,
                tabs: [
                  Tab(text: l.ordernewTabBasic),
                  Tab(text: l.ordernewTabTravel),
                  Tab(text: l.ordernewTabEmergency),
                ],
              ),
            ),
            // Form
            Expanded(
              child: TabBarView(
                controller: _tabCtrl,
                children: [
                  _BasicTab(l: l, surnameCtrl: _surnameCtrl, givenCtrl: _givenCtrl,
                      dobCtrl: _dobCtrl, nationalityCtrl: _nationalityCtrl,
                      passportNoCtrl: _passportNoCtrl, passportExpCtrl: _passportExpCtrl,
                      errors: _errors),
                  _TravelTab(l: l, arrivalCtrl: _arrivalCtrl, departureCtrl: _departureCtrl, purposeCtrl: _purposeCtrl),
                  _EmergencyTab(l: l, nameCtrl: _emergencyNameCtrl, phoneCtrl: _emergencyPhoneCtrl, relCtrl: _emergencyRelCtrl),
                ],
              ),
            ),
            // Bottom CTA
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, -2))],
              ),
              child: SafeArea(
                top: false,
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _loading ? null : _onSubmit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3B6EF5),
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      padding: const EdgeInsets.symmetric(vertical: 15),
                    ),
                    child: _loading
                        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : Text(l.ordernewSubmit, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BasicTab extends StatelessWidget {
  final AppLocalizations l;
  final TextEditingController surnameCtrl, givenCtrl, dobCtrl, nationalityCtrl, passportNoCtrl, passportExpCtrl;
  final Map<String, String> errors;

  const _BasicTab({required this.l, required this.surnameCtrl, required this.givenCtrl,
      required this.dobCtrl, required this.nationalityCtrl, required this.passportNoCtrl,
      required this.passportExpCtrl, required this.errors});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.ordernewSectionBasic, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
          const SizedBox(height: 16),
          _field(l.ordernewFieldSurname, surnameCtrl, error: errors['surname']),
          _field(l.ordernewFieldGiven, givenCtrl, error: errors['given']),
          _field(l.ordernewFieldDob, dobCtrl, placeholder: 'YYYY-MM-DD'),
          _field(l.ordernewFieldNationality, nationalityCtrl),
          _field(l.ordernewFieldPassportNo, passportNoCtrl, error: errors['passportNo']),
          _field(l.ordernewFieldPassportExp, passportExpCtrl, placeholder: 'YYYY-MM-DD'),
        ],
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl, {String? error, String? placeholder}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF374151))),
          const SizedBox(height: 6),
          TextField(
            controller: ctrl,
            decoration: InputDecoration(
              hintText: placeholder ?? label,
              hintStyle: const TextStyle(color: Color(0xFF9CA3AF)),
              filled: true, fillColor: Colors.white,
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: error != null ? const Color(0xFFEF4444) : const Color(0xFFE5E7EB))),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: error != null ? const Color(0xFFEF4444) : const Color(0xFFE5E7EB))),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B6EF5))),
            ),
          ),
          if (error != null) Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(error, style: const TextStyle(fontSize: 12, color: Color(0xFFEF4444))),
          ),
        ],
      ),
    );
  }
}

class _TravelTab extends StatelessWidget {
  final AppLocalizations l;
  final TextEditingController arrivalCtrl, departureCtrl, purposeCtrl;

  const _TravelTab({required this.l, required this.arrivalCtrl, required this.departureCtrl, required this.purposeCtrl});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.ordernewSectionTravel, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
          const SizedBox(height: 16),
          _field(l.ordernewFieldArrival, arrivalCtrl, 'YYYY-MM-DD'),
          _field(l.ordernewFieldDeparture, departureCtrl, 'YYYY-MM-DD'),
          _field(l.ordernewFieldPurpose, purposeCtrl),
        ],
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl, [String? hint]) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF374151))),
          const SizedBox(height: 6),
          TextField(
            controller: ctrl,
            decoration: InputDecoration(
              hintText: hint ?? label,
              hintStyle: const TextStyle(color: Color(0xFF9CA3AF)),
              filled: true, fillColor: Colors.white,
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B6EF5))),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmergencyTab extends StatelessWidget {
  final AppLocalizations l;
  final TextEditingController nameCtrl, phoneCtrl, relCtrl;

  const _EmergencyTab({required this.l, required this.nameCtrl, required this.phoneCtrl, required this.relCtrl});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l.ordernewSectionEmergency, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E))),
          const SizedBox(height: 16),
          _field(l.ordernewFieldEmergencyName, nameCtrl),
          _field(l.ordernewFieldEmergencyPhone, phoneCtrl),
          _field(l.ordernewFieldEmergencyRel, relCtrl),
        ],
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF374151))),
          const SizedBox(height: 6),
          TextField(
            controller: ctrl,
            decoration: InputDecoration(
              hintText: label,
              hintStyle: const TextStyle(color: Color(0xFF9CA3AF)),
              filled: true, fillColor: Colors.white,
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
              focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF3B6EF5))),
            ),
          ),
        ],
      ),
    );
  }
}
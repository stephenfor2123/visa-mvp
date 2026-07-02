// ApplyPage — 4-step order wizard (W32 port of frontend/web/src/views/Apply.vue).
//
// Flow:
//   Step 1: pick a country (grouped: hero national / schengen 26)
//   Step 2: review RAG-pulled materials checklist + fee/validity/process chips
//   Step 3: fill in basic trip info (visa_type, dates, departure city, contact)
//   Step 4: confirm + create order → OrderDetailPage

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../services/apply_service.dart';
import '../services/auth_service.dart';
import '../services/destinations_service.dart';
import '../services/rag_service.dart';
import 'order_detail_page.dart';

class ApplyPage extends StatefulWidget {
  /// Optional pre-selected country (deep-link from HomePage hero CTA).
  final String? initialCountryCode;
  const ApplyPage({super.key, this.initialCountryCode});

  @override
  State<ApplyPage> createState() => _ApplyPageState();
}

class _ApplyPageState extends State<ApplyPage> {
  int _step = 1;
  bool _loading = false;
  String? _error;

  String? _countryCode;
  Checklist? _checklist;
  // Start with fallback so step-1 renders immediately even before API returns.
  final _destSvc = DestinationsService();
  List<Destination> _allCountries = DestinationsService.fallback();
  late Map<String, List<Destination>> _grouped =
      _destSvc.groupByVisaType(_allCountries);

  // Step 3 form
  String _visaType = 'tourism';
  DateTime? _dateFrom;
  DateTime? _dateTo;
  final _departureCityCtrl = TextEditingController();
  final _emergencyCtrl = TextEditingController();
  final _purposeCtrl = TextEditingController();

  final _ragSvc = RAGService();
  final _applySvc = ApplyService();

  @override
  void initState() {
    super.initState();
    // W35: allow ?country=XX URL deep-link (testing hook).
    final urlCc = Uri.base.queryParameters['country'];
    final cc = (widget.initialCountryCode != null && widget.initialCountryCode!.isNotEmpty)
        ? widget.initialCountryCode
        : (urlCc != null && urlCc.isNotEmpty ? urlCc : null);
    if (cc != null) {
      _countryCode = cc;
      // Defer to next frame so setState is valid.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        setState(() => _step = 2);
        _loadChecklist();
      });
    }
    _loadCountries();
  }

  @override
  void dispose() {
    _departureCityCtrl.dispose();
    _emergencyCtrl.dispose();
    _purposeCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadCountries() async {
    setState(() => _loading = true);
    try {
      final list = await _destSvc.list(lang: 'zh-CN');
      final all = list.isNotEmpty ? list : DestinationsService.fallback();
      setState(() {
        _allCountries = all;
        _grouped = _destSvc.groupByVisaType(all);
      });
    } catch (_) {
      // API failed — keep fallback values (initState already populated _grouped).
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadChecklist() async {
    if (_countryCode == null) return;
    setState(() {
      _loading = true;
      _error = null;
      _checklist = null;
    });
    try {
      final token = await AuthService.getAccessToken();
      if (token == null) throw '请先登录';
      final cl = await _ragSvc.checklist(countryCode: _countryCode!, accessToken: token);
      setState(() => _checklist = cl);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _selectCountry(String cc) {
    setState(() {
      _countryCode = cc;
      _step = 2;
    });
    _loadChecklist();
  }

  void _goNext() {
    if (_step < 4) setState(() => _step += 1);
  }

  void _goBack() {
    if (_step > 1) setState(() => _step -= 1);
  }

  Future<void> _submit() async {
    if (_countryCode == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final token = await AuthService.getAccessToken();
      if (token == null) throw '请先登录';
      final draft = OrderDraft(
        countryCode: _countryCode!,
        visaType: _visaType,
        travelDateFrom: _dateFrom?.toIso8601String().substring(0, 10),
        travelDateTo: _dateTo?.toIso8601String().substring(0, 10),
        departureCity: _departureCityCtrl.text.trim().isEmpty ? null : _departureCityCtrl.text.trim(),
        emergencyContact: _emergencyCtrl.text.trim().isEmpty ? null : _emergencyCtrl.text.trim(),
        purposeOfTrip: _purposeCtrl.text.trim().isEmpty ? null : _purposeCtrl.text.trim(),
      );
      final order = await _applySvc.createOrder(draft: draft, accessToken: token);
      if (!mounted) return;
      // Navigate to OrderDetailPage.
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => OrderDetailPage(orderNo: order.orderNo)),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: Text(
          _stepTitle(l, _step),
          style: const TextStyle(color: Color(0xFF0F172A), fontSize: 16, fontWeight: FontWeight.w600),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(
            value: _step / 4,
            backgroundColor: const Color(0xFFE2E8F0),
            valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF3B6EF5)),
          ),
        ),
      ),
      body: _buildStep(),
    );
  }

  String _stepTitle(AppLocalizations l, int step) {
    switch (step) {
      case 1: return '选择目的地';
      case 2: return '材料清单';
      case 3: return '出行信息';
      case 4: return '确认申请';
      default: return '申请签证';
    }
  }

  Widget _buildStep() {
    if (_loading && _allCountries.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    switch (_step) {
      case 1: return _buildCountryStep();
      case 2: return _buildChecklistStep();
      case 3: return _buildTripInfoStep();
      case 4: return _buildConfirmStep();
      default: return const SizedBox.shrink();
    }
  }

  // ─── Step 1: Country picker ──────────────────────────────────────────────────

  Widget _buildCountryStep() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          '你想去哪里？',
          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Color(0xFF0F172A)),
        ),
        const SizedBox(height: 4),
        const Text(
          '选一个国家，看看你需要准备什么。',
          style: TextStyle(fontSize: 14, color: Color(0xFF64748B)),
        ),
        const SizedBox(height: 24),
        if (_grouped['national']?.isNotEmpty ?? false) ...[
          _groupHeader('精选目的地', _grouped['national']!.length),
          const SizedBox(height: 12),
          _countryGrid(_grouped['national']!),
          const SizedBox(height: 24),
        ],
        if (_grouped['schengen']?.isNotEmpty ?? false) ...[
          _groupHeader('申根 26 国', _grouped['schengen']!.length),
          const SizedBox(height: 12),
          _countryGrid(_grouped['schengen']!),
        ],
      ],
    );
  }

  Widget _groupHeader(String title, int count) {
    return Row(
      children: [
        Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF475569), letterSpacing: 0.3)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
          decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(999)),
          child: Text('$count', style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8), fontWeight: FontWeight.w500)),
        ),
      ],
    );
  }

  Widget _countryGrid(List<Destination> items) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
        childAspectRatio: 1.05,
      ),
      itemCount: items.length,
      itemBuilder: (_, i) => _countryTile(items[i]),
    );
  }

  Widget _countryTile(Destination d) {
    final flag = _flagOf(d.countryCode);
    return InkWell(
      onTap: () => _selectCountry(d.countryCode),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFFF8FAFC),
          border: Border.all(color: const Color(0xFFE2E8F0)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(flag, style: const TextStyle(fontSize: 28)),
            const SizedBox(height: 6),
            Text(
              d.countryName,
              style: const TextStyle(fontSize: 12, color: Color(0xFF0F172A), fontWeight: FontWeight.w500),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }

  String _flagOf(String cc) {
    const flags = {
      'US': '🇺🇸', 'JP': '🇯🇵', 'KR': '🇰🇷', 'SG': '🇸🇬', 'GB': '🇬🇧', 'FR': '🇫🇷',
      'ID': '🇮🇩', 'VN': '🇻🇳', 'TH': '🇹🇭', 'DE': '🇩🇪', 'AU': '🇦🇺', 'CA': '🇨🇦',
      'NZ': '🇳🇿', 'SCHENGEN': '🇪🇺',
      'AT': '🇦🇹', 'BE': '🇧🇪', 'HR': '🇭🇷', 'CZ': '🇨🇿', 'DK': '🇩🇰', 'EE': '🇪🇪',
      'FI': '🇫🇮', 'GR': '🇬🇷', 'HU': '🇭🇺', 'IS': '🇮🇸', 'IT': '🇮🇹', 'LV': '🇱🇻',
      'LI': '🇱🇮', 'LT': '🇱🇹', 'LU': '🇱🇺', 'MT': '🇲🇹', 'NL': '🇳🇱', 'NO': '🇳🇴',
      'PL': '🇵🇱', 'PT': '🇵🇹', 'SK': '🇸🇰', 'SI': '🇸🇮', 'ES': '🇪🇸', 'SE': '🇸🇪',
    };
    return flags[cc] ?? '🌐';
  }

  // ─── Step 2: Checklist ───────────────────────────────────────────────────────

  Widget _buildChecklistStep() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Color(0xFF94A3B8)),
            const SizedBox(height: 12),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadChecklist, child: const Text('重试')),
          ],
        ),
      );
    }
    final cl = _checklist;
    if (cl == null) return const SizedBox.shrink();
    final cc = _allCountries.firstWhere((d) => d.countryCode == _countryCode, orElse: () => DestinationsService.fallback().first);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Text(_flagOf(cc.countryCode), style: const TextStyle(fontSize: 22)),
            const SizedBox(width: 6),
            Text(
              cc.countryName,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF0F172A)),
            ),
            const SizedBox(width: 6),
            const Text('· 材料清单', style: TextStyle(fontSize: 18, color: Color(0xFF64748B))),
          ],
        ),
        const SizedBox(height: 16),
        if (cl.fee != null || cl.processingTime != null || cl.validity != null)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(12)),
            child: Row(
              children: [
                if (cl.fee != null) _metaCell('费用', cl.fee!),
                if (cl.processingTime != null) ...[
                  const SizedBox(width: 12),
                  _metaCell('处理时间', cl.processingTime!),
                ],
                if (cl.validity != null) ...[
                  const SizedBox(width: 12),
                  _metaCell('有效期', cl.validity!),
                ],
              ],
            ),
          ),
        const SizedBox(height: 16),
        ...cl.materials.map((m) => _materialTile(m)),
        const SizedBox(height: 24),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _goBack,
                style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                child: const Text('← 上一步'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                onPressed: _goNext,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3B6EF5),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: const Text('下一步：填表'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _metaCell(String label, String value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
          const SizedBox(height: 2),
          Text(
            value,
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF0F172A), height: 1.3),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _materialTile(ChecklistMaterial m) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(color: Colors.white, border: Border.all(color: const Color(0xFFE2E8F0)), borderRadius: BorderRadius.circular(10)),
      child: Row(
        children: [
          Icon(m.required ? Icons.check_circle : Icons.radio_button_unchecked,
              size: 18, color: m.required ? const Color(0xFF3B6EF5) : const Color(0xFF94A3B8)),
          const SizedBox(width: 10),
          Expanded(child: Text(m.name, style: const TextStyle(fontSize: 14, color: Color(0xFF0F172A)))),
          if (m.required)
            const Text('必', style: TextStyle(fontSize: 10, color: Color(0xFFEF4444), fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  // ─── Step 3: Trip info ──────────────────────────────────────────────────────

  Widget _buildTripInfoStep() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('出行信息', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        const SizedBox(height: 16),
        _label('签证类型'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: ['tourism', 'business', 'student', 'family', 'other']
              .map((v) => ChoiceChip(
                    label: Text(_visaTypeLabel(v)),
                    selected: _visaType == v,
                    onSelected: (_) => setState(() => _visaType = v),
                  ))
              .toList(),
        ),
        const SizedBox(height: 16),
        _label('出发日期'),
        const SizedBox(height: 8),
        _datePicker(_dateFrom, (d) => setState(() => _dateFrom = d), '选择出发日期'),
        const SizedBox(height: 12),
        _label('返回日期'),
        const SizedBox(height: 8),
        _datePicker(_dateTo, (d) => setState(() => _dateTo = d), '选择返回日期'),
        const SizedBox(height: 16),
        _label('出发城市'),
        const SizedBox(height: 8),
        TextField(controller: _departureCityCtrl, decoration: const InputDecoration(hintText: '如：上海', border: OutlineInputBorder())),
        const SizedBox(height: 12),
        _label('紧急联系人'),
        const SizedBox(height: 8),
        TextField(controller: _emergencyCtrl, decoration: const InputDecoration(hintText: '如：张三 +86 138xxxx', border: OutlineInputBorder())),
        const SizedBox(height: 12),
        _label('出行目的'),
        const SizedBox(height: 8),
        TextField(controller: _purposeCtrl, maxLines: 3, decoration: const InputDecoration(hintText: '简要说明出行目的', border: OutlineInputBorder())),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _goNext,
          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF3B6EF5), padding: const EdgeInsets.symmetric(vertical: 14)),
          child: const Text('下一步：确认'),
        ),
        const SizedBox(height: 8),
        TextButton(onPressed: _goBack, child: const Text('← 上一步')),
      ],
    );
  }

  Widget _label(String t) => Text(t, style: const TextStyle(fontSize: 13, color: Color(0xFF475569), fontWeight: FontWeight.w500));

  Widget _datePicker(DateTime? value, void Function(DateTime) onPicked, String hint) {
    return InkWell(
      onTap: () async {
        final d = await showDatePicker(
          context: context,
          initialDate: value ?? DateTime.now().add(const Duration(days: 30)),
          firstDate: DateTime.now(),
          lastDate: DateTime.now().add(const Duration(days: 365 * 2)),
        );
        if (d != null) onPicked(d);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        decoration: BoxDecoration(border: Border.all(color: const Color(0xFFCBD5E1)), borderRadius: BorderRadius.circular(4)),
        child: Row(
          children: [
            const Icon(Icons.calendar_today, size: 16, color: Color(0xFF64748B)),
            const SizedBox(width: 8),
            Text(value == null ? hint : value.toIso8601String().substring(0, 10),
                style: TextStyle(fontSize: 14, color: value == null ? const Color(0xFF94A3B8) : const Color(0xFF0F172A))),
          ],
        ),
      ),
    );
  }

  String _visaTypeLabel(String v) {
    switch (v) {
      case 'tourism': return '旅游';
      case 'business': return '商务';
      case 'student': return '留学';
      case 'family': return '探亲';
      default: return '其他';
    }
  }

  // ─── Step 4: Confirm ────────────────────────────────────────────────────────

  Widget _buildConfirmStep() {
    if (_error != null) {
      return Center(child: Text(_error!, style: const TextStyle(color: Colors.red)));
    }
    final cc = _allCountries.firstWhere((d) => d.countryCode == _countryCode, orElse: () => DestinationsService.fallback().first);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('确认申请', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        const SizedBox(height: 16),
        _confirmRow('目的地', '${_flagOf(cc.countryCode)} ${cc.countryName}'),
        _confirmRow('签证类型', _visaTypeLabel(_visaType)),
        _confirmRow('出发', _dateFrom?.toIso8601String().substring(0, 10) ?? '—'),
        _confirmRow('返回', _dateTo?.toIso8601String().substring(0, 10) ?? '—'),
        _confirmRow('城市', _departureCityCtrl.text.trim().isEmpty ? '—' : _departureCityCtrl.text.trim()),
        if (_emergencyCtrl.text.trim().isNotEmpty) _confirmRow('紧急联系人', _emergencyCtrl.text.trim()),
        if (_purposeCtrl.text.trim().isNotEmpty) _confirmRow('出行目的', _purposeCtrl.text.trim()),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: _loading ? null : _submit,
          style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF3B6EF5), padding: const EdgeInsets.symmetric(vertical: 16)),
          child: Text(_loading ? '提交中…' : '确认提交'),
        ),
        const SizedBox(height: 8),
        TextButton(onPressed: _goBack, child: const Text('← 上一步')),
      ],
    );
  }

  Widget _confirmRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 80, child: Text(label, style: const TextStyle(fontSize: 13, color: Color(0xFF64748B)))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 14, color: Color(0xFF0F172A)))),
        ],
      ),
    );
  }
}
// PassportReviewPage — confirm/edit OCR-extracted passport fields.
// Mirrors frontend/web/src/views/PassportReview.vue.

import 'dart:io';
import 'package:flutter/material.dart';
import '../services/ocr_service.dart';

class PassportReviewPage extends StatefulWidget {
  final File image;
  final OCRResult ocr;
  const PassportReviewPage({super.key, required this.image, required this.ocr});

  @override
  State<PassportReviewPage> createState() => _PassportReviewPageState();
}

class _PassportReviewPageState extends State<PassportReviewPage> {
  late final TextEditingController _passportNo;
  late final TextEditingController _surname;
  late final TextEditingController _givenName;
  late final TextEditingController _sex;
  late final TextEditingController _nationality;
  late final TextEditingController _dob;
  late final TextEditingController _expiry;

  @override
  void initState() {
    super.initState();
    final f = widget.ocr.fields;
    _passportNo = TextEditingController(text: f.passportNo ?? '');
    _surname = TextEditingController(text: f.surname ?? '');
    _givenName = TextEditingController(text: f.givenName ?? '');
    _sex = TextEditingController(text: f.sex ?? '');
    _nationality = TextEditingController(text: f.nationality ?? '');
    _dob = TextEditingController(text: f.dob ?? '');
    _expiry = TextEditingController(text: f.expiry ?? '');
  }

  @override
  void dispose() {
    _passportNo.dispose();
    _surname.dispose();
    _givenName.dispose();
    _sex.dispose();
    _nationality.dispose();
    _dob.dispose();
    _expiry.dispose();
    super.dispose();
  }

  void _confirm() {
    final data = {
      'passport_no': _passportNo.text,
      'surname': _surname.text,
      'given_name': _givenName.text,
      'sex': _sex.text,
      'nationality': _nationality.text,
      'dob': _dob.text,
      'expiry': _expiry.text,
    };
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('已确认'),
        content: const Text('护照信息已保存到订单。可以继续补充材料。'),
        actions: [
          TextButton(onPressed: () { Navigator.of(context).pop(); Navigator.of(context).pop(data); }, child: const Text('好的')),
        ],
      ),
    );
  }

  void _retake() {
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final f = widget.ocr.fields;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _retake,
        ),
        title: const Text('确认护照信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Top: image preview + retake
          Stack(
            alignment: Alignment.bottomRight,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(widget.image, height: 200, fit: BoxFit.cover, width: double.infinity),
              ),
              Padding(
                padding: const EdgeInsets.all(8),
                child: ElevatedButton.icon(
                  onPressed: _retake,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white.withOpacity(0.9),
                    foregroundColor: const Color(0xFF0F172A),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('重拍', style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            f.isPassportDoc ? '✓ 已识别为护照' : '⚠️ 未识别为护照',
            style: TextStyle(fontSize: 12, color: f.isPassportDoc ? const Color(0xFF10B981) : const Color(0xFFF59E0B)),
          ),
          const SizedBox(height: 16),
          _field('护照号', _passportNo, required: true),
          _field('姓 (Surname)', _surname),
          _field('名 (Given Name)', _givenName),
          _field('性别 (M / F)', _sex),
          _field('国籍', _nationality),
          _field('出生日期 (YYYY-MM-DD)', _dob),
          _field('有效期至 (YYYY-MM-DD)', _expiry),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: _confirm,
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF3B6EF5), padding: const EdgeInsets.symmetric(vertical: 14)),
            child: const Text('确认，下一步'),
          ),
          const SizedBox(height: 8),
          TextButton(onPressed: _retake, child: const Text('← 重新拍照')),
        ],
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl, {bool required = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(label, style: const TextStyle(fontSize: 13, color: Color(0xFF475569), fontWeight: FontWeight.w500)),
            if (required) const Text(' *', style: TextStyle(color: Color(0xFFEF4444))),
          ]),
          const SizedBox(height: 6),
          TextField(
            controller: ctrl,
            decoration: const InputDecoration(border: OutlineInputBorder(), isDense: true),
          ),
        ],
      ),
    );
  }
}
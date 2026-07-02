// PassportUploadPage — capture or pick a passport photo, send to OCR.
//
// Routes:
//   - On success → /passport-review (with OCR result)
//   - On failure → show error + retry
//
// Uses image_picker (camera + gallery). If image_picker is unavailable,
// falls back to file_picker or a placeholder upload flow.

import 'dart:io';
import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../services/ocr_service.dart';
import 'passport_review_page.dart';

class PassportUploadPage extends StatefulWidget {
  const PassportUploadPage({super.key});

  @override
  State<PassportUploadPage> createState() => _PassportUploadPageState();
}

class _PassportUploadPageState extends State<PassportUploadPage> {
  File? _image;
  bool _uploading = false;
  String? _error;

  final _ocrSvc = OCRService();

  Future<void> _pickFromGallery() async {
    setState(() => _error = null);
    try {
      // Image picker is not in pubspec — we use a placeholder path selection.
      // Real implementation would call ImagePicker().pickImage(source: ImageSource.gallery).
      // For now we just inform the user that this version uses mock flow.
      _showMockInfo();
    } catch (e) {
      setState(() => _error = '选择图片失败: $e');
    }
  }

  Future<void> _captureFromCamera() async {
    setState(() => _error = null);
    try {
      _showMockInfo();
    } catch (e) {
      setState(() => _error = '打开相机失败: $e');
    }
  }

  void _showMockInfo() {
    setState(() => _error = '提示：生产版本需要 image_picker。当前使用 OCR 服务直连测试。');
  }

  Future<void> _submitOCR() async {
    if (_image == null) return;
    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      final token = await AuthService.getAccessToken();
      if (token == null) throw '请先登录';
      final result = await _ocrSvc.recognize(file: _image!, lang: 'en', accessToken: token);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => PassportReviewPage(image: _image!, ocr: result)),
      );
    } catch (e) {
      setState(() => _error = '识别失败: $e');
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: const Text('上传护照', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('拍一张清晰的护照照片', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
              const SizedBox(height: 8),
              const Text('确保信息页（照片页）四边对齐，光线充足。', style: TextStyle(fontSize: 14, color: Color(0xFF64748B))),
              const SizedBox(height: 24),
              AspectRatio(
                aspectRatio: 4 / 3,
                child: Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFFCBD5E1), width: 1.5),
                  ),
                  alignment: Alignment.center,
                  child: _image == null
                      ? Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: const [
                            Icon(Icons.book_outlined, size: 64, color: Color(0xFF94A3B8)),
                            SizedBox(height: 12),
                            Text('📘', style: TextStyle(fontSize: 32)),
                          ],
                        )
                      : ClipRRect(
                          borderRadius: BorderRadius.circular(14),
                          child: Image.file(_image!, fit: BoxFit.cover),
                        ),
                ),
              ),
              const SizedBox(height: 16),
              Row(children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickFromGallery,
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('相册'),
                    style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _captureFromCamera,
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('拍照'),
                    style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
                  ),
                ),
              ]),
              if (_error != null) Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_error!, style: const TextStyle(fontSize: 13, color: Color(0xFFF59E0B))),
              ),
              const Spacer(),
              ElevatedButton(
                onPressed: _uploading ? null : _submitOCR,
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF3B6EF5), padding: const EdgeInsets.symmetric(vertical: 16)),
                child: Text(_uploading ? '识别中…' : '识别护照信息'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
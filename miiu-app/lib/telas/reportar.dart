import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../modelos.dart';
import '../rotulos.dart';
import '../servicos/api.dart';
import '../servicos/armazenamento.dart';
import '../servicos/localizacao.dart';

/// Percepcao e reporte: foto + localizacao automatica + classe informada.
/// Devolve o protocolo (via Navigator.pop) quando o envio da certo.
class TelaReportar extends StatefulWidget {
  const TelaReportar({super.key});

  @override
  State<TelaReportar> createState() => _TelaReportarState();
}

class _TelaReportarState extends State<TelaReportar> {
  static const double _precisaoBoaM = 30;

  final ImagePicker _seletor = ImagePicker();
  final TextEditingController _descricao = TextEditingController();

  // bytes da foto: servem para a previa e para o envio, no Android e na web
  Uint8List? _foto;
  Position? _posicao;
  String? _erroGps;
  bool _localizando = false;
  String? _classe;
  bool _enviando = false;

  @override
  void initState() {
    super.initState();
    // comeca a buscar o GPS enquanto o cidadao enquadra a foto
    WidgetsBinding.instance.addPostFrameCallback((_) => _localizar());
  }

  @override
  void dispose() {
    _descricao.dispose();
    super.dispose();
  }

  Future<void> _localizar() async {
    setState(() {
      _localizando = true;
      _erroGps = null;
    });
    final erro = await Localizacao.garantirPermissao();
    if (erro != null) {
      if (mounted) {
        setState(() {
          _erroGps = erro;
          _localizando = false;
        });
      }
      return;
    }
    try {
      final posicao = await Localizacao.posicaoAtual();
      if (mounted) setState(() => _posicao = posicao);
    } catch (_) {
      if (mounted) {
        setState(() => _erroGps = 'Não foi possível obter a localização. Tente de novo ao ar livre.');
      }
    } finally {
      if (mounted) setState(() => _localizando = false);
    }
  }

  Future<void> _escolherFoto(ImageSource origem) async {
    try {
      final foto = await _seletor.pickImage(
        source: origem,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
      );
      if (foto == null) return;
      final bytes = await foto.readAsBytes();
      if (mounted) setState(() => _foto = bytes);
    } on PlatformException catch (e) {
      _avisar('Não foi possível abrir a câmera: ${e.message ?? e.code}');
    }
  }

  void _avisar(String texto) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(texto)));
  }

  bool get _podeEnviar => _foto != null && _posicao != null && _classe != null && !_enviando;

  Future<void> _enviar() async {
    final foto = _foto;
    final posicao = _posicao;
    final classe = _classe;
    if (foto == null || posicao == null || classe == null) return;

    setState(() => _enviando = true);
    try {
      final criada = await Api.reportar(
        imagem: foto,
        latitude: posicao.latitude,
        longitude: posicao.longitude,
        precisaoM: posicao.accuracy,
        classe: classe,
        descricao: _descricao.text,
      );
      await Armazenamento.adicionarProtocolo(criada.protocolo);
      if (!mounted) return;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(builder: (_) => TelaRecibo(criada: criada)),
      );
      if (mounted) Navigator.of(context).pop(criada.protocolo);
    } on ErroApi catch (e) {
      _avisar(e.mensagem);
    } catch (e) {
      _avisar('Falha ao enviar o reporte: $e');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Widget _secaoFoto(BuildContext context) {
    final foto = _foto;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (foto != null)
            AspectRatio(
              aspectRatio: 4 / 3,
              child: Image.memory(foto, fit: BoxFit.cover),
            )
          else
            Container(
              height: 160,
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              alignment: Alignment.center,
              child: const Text('Fotografe o problema de perto e com boa luz'),
            ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: _enviando ? null : () => _escolherFoto(ImageSource.camera),
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: Text(foto == null ? 'Tirar foto' : 'Tirar outra'),
                ),
                // A galeria existe so na versao de desenvolvimento, para testes
                // no emulador: o reporte real usa a foto tirada no local.
                if (kDebugMode)
                  OutlinedButton.icon(
                    onPressed: _enviando ? null : () => _escolherFoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Galeria (teste)'),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _secaoLocalizacao(BuildContext context) {
    final posicao = _posicao;
    final String texto;
    IconData icone = Icons.location_searching;
    if (_localizando) {
      texto = 'Obtendo a localização…';
    } else if (_erroGps != null) {
      texto = _erroGps!;
      icone = Icons.location_disabled;
    } else if (posicao != null) {
      final precisa = posicao.accuracy <= _precisaoBoaM;
      icone = precisa ? Icons.location_on : Icons.location_on_outlined;
      texto = '${posicao.latitude.toStringAsFixed(6)}, ${posicao.longitude.toStringAsFixed(6)}\n'
          'Precisão de ±${posicao.accuracy.round()} m'
          '${precisa ? '' : ' (fraca: se puder, aguarde e atualize)'}';
    } else {
      texto = 'Localização ainda não obtida.';
    }
    return Card(
      child: ListTile(
        leading: Icon(icone),
        title: const Text('Local da ocorrência'),
        subtitle: Text(texto),
        trailing: _localizando
            ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2))
            : IconButton(
                tooltip: 'Atualizar localização',
                onPressed: _enviando ? null : _localizar,
                icon: const Icon(Icons.refresh),
              ),
      ),
    );
  }

  Widget _secaoClasse(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('O que você encontrou?', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final entrada in rotulosClasse.entries)
                  ChoiceChip(
                    label: Text(entrada.value),
                    selected: _classe == entrada.key,
                    onSelected: _enviando
                        ? null
                        : (marcado) => setState(() => _classe = marcado ? entrada.key : null),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descricao,
              enabled: !_enviando,
              maxLength: 500,
              maxLines: 3,
              minLines: 1,
              decoration: const InputDecoration(
                labelText: 'Descrição (opcional)',
                hintText: 'Ex.: buraco na faixa da direita, perto do semáforo',
                border: OutlineInputBorder(),
              ),
            ),
            Text(
              'Não escreva nomes, telefones ou outros dados pessoais.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reportar problema')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            _secaoFoto(context),
            const SizedBox(height: 8),
            _secaoLocalizacao(context),
            const SizedBox(height: 8),
            _secaoClasse(context),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _podeEnviar ? _enviar : null,
              icon: _enviando
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send),
              label: Text(_enviando ? 'Enviando…' : 'Enviar reporte'),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            ),
            if (!_podeEnviar && !_enviando)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  'Para enviar: tire a foto, aguarde a localização e escolha o tipo do problema.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Comprovante do reporte com o numero de protocolo.
class TelaRecibo extends StatelessWidget {
  final OcorrenciaCriada criada;

  const TelaRecibo({super.key, required this.criada});

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final detectada = criada.classeDetectada;
    return Scaffold(
      appBar: AppBar(title: const Text('Reporte enviado'), automaticallyImplyLeading: false),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const Icon(Icons.check_circle_outline, size: 72),
            const SizedBox(height: 16),
            Text('Obrigado por colaborar!', style: tema.textTheme.headlineSmall, textAlign: TextAlign.center),
            const SizedBox(height: 24),
            Text('Seu número de protocolo', style: tema.textTheme.bodyMedium, textAlign: TextAlign.center),
            const SizedBox(height: 4),
            SelectableText(
              criada.protocolo,
              textAlign: TextAlign.center,
              style: tema.textTheme.headlineMedium?.copyWith(
                fontFamily: 'monospace',
                fontWeight: FontWeight.w700,
              ),
            ),
            TextButton.icon(
              onPressed: () async {
                await Clipboard.setData(ClipboardData(text: criada.protocolo));
                if (context.mounted) {
                  ScaffoldMessenger.of(context)
                      .showSnackBar(const SnackBar(content: Text('Protocolo copiado')));
                }
              },
              icon: const Icon(Icons.copy),
              label: const Text('Copiar protocolo'),
            ),
            const SizedBox(height: 16),
            Text(criada.mensagem, textAlign: TextAlign.center),
            if (detectada != null) ...[
              const SizedBox(height: 12),
              Text(
                'Análise automática da foto: ${rotuloClasse(detectada)} '
                '(${formatarPorcentagem(criada.confianca)} de confiança).',
                textAlign: TextAlign.center,
                style: tema.textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 32),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Concluir'),
            ),
            const SizedBox(height: 8),
            Text(
              'Você pode acompanhar o andamento na aba "Meus reportes".',
              textAlign: TextAlign.center,
              style: tema.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

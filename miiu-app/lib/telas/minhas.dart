import 'package:flutter/material.dart';

import '../estado.dart';
import '../modelos.dart';
import '../rotulos.dart';
import '../servicos/api.dart';
import '../servicos/armazenamento.dart';
import '../widgets/selo_status.dart';
import 'detalhe.dart';

/// Acompanhamento dos reportes feitos neste aparelho e consulta por protocolo.
class TelaMinhas extends StatefulWidget {
  const TelaMinhas({super.key});

  @override
  State<TelaMinhas> createState() => _TelaMinhasState();
}

class _ItemReporte {
  final String protocolo;
  final OcorrenciaPublica? ocorrencia;
  final String? erro;

  _ItemReporte(this.protocolo, {this.ocorrencia, this.erro});
}

class _TelaMinhasState extends State<TelaMinhas> {
  final TextEditingController _consulta = TextEditingController();
  List<_ItemReporte> _itens = <_ItemReporte>[];
  bool _carregando = false;

  @override
  void initState() {
    super.initState();
    Estado.versaoReportes.addListener(_carregar);
    WidgetsBinding.instance.addPostFrameCallback((_) => _carregar());
  }

  @override
  void dispose() {
    Estado.versaoReportes.removeListener(_carregar);
    _consulta.dispose();
    super.dispose();
  }

  Future<_ItemReporte> _buscar(String protocolo) async {
    try {
      return _ItemReporte(protocolo, ocorrencia: await Api.consultar(protocolo));
    } on ErroApi catch (e) {
      return _ItemReporte(protocolo, erro: e.mensagem);
    } catch (_) {
      return _ItemReporte(protocolo, erro: 'Resposta inesperada do servidor.');
    }
  }

  Future<void> _carregar() async {
    if (!mounted) return;
    setState(() => _carregando = true);
    final itens = await Future.wait(Armazenamento.protocolos.map(_buscar));
    if (!mounted) return;
    setState(() {
      _itens = itens;
      _carregando = false;
    });
  }

  void _abrir(String protocolo) {
    Navigator.of(context).push<void>(
      MaterialPageRoute(builder: (_) => TelaDetalhe(protocolo: protocolo)),
    );
  }

  void _consultarDigitado() {
    final protocolo = normalizarProtocolo(_consulta.text);
    if (protocolo.isEmpty) return;
    FocusScope.of(context).unfocus();
    _abrir(protocolo);
  }

  Future<void> _remover(String protocolo) async {
    await Armazenamento.removerProtocolo(protocolo);
    if (!mounted) return;
    setState(() => _itens = _itens.where((i) => i.protocolo != protocolo).toList());
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$protocolo removido da lista'),
        action: SnackBarAction(
          label: 'Desfazer',
          onPressed: () async {
            await Armazenamento.adicionarProtocolo(protocolo);
            await _carregar();
          },
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Meus reportes')),
      body: RefreshIndicator(
        onRefresh: _carregar,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(12),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 4, 4, 4),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _consulta,
                        textCapitalization: TextCapitalization.characters,
                        decoration: const InputDecoration(
                          hintText: 'Consultar protocolo (MIIU-2026-…)',
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _consultarDigitado(),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Consultar',
                      onPressed: _consultarDigitado,
                      icon: const Icon(Icons.search),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            if (_carregando) const LinearProgressIndicator(),
            if (!_carregando && _itens.isEmpty)
              const Padding(
                padding: EdgeInsets.all(32),
                child: Text(
                  'Você ainda não fez nenhum reporte neste aparelho.\n'
                  'Use o botão "Reportar problema" no mapa.',
                  textAlign: TextAlign.center,
                ),
              ),
            for (final item in _itens)
              Dismissible(
                key: ValueKey(item.protocolo),
                direction: DismissDirection.endToStart,
                background: Container(
                  alignment: Alignment.centerRight,
                  padding: const EdgeInsets.only(right: 20),
                  child: const Icon(Icons.delete_outline),
                ),
                onDismissed: (_) => _remover(item.protocolo),
                child: Card(
                  child: ListTile(
                    onTap: () => _abrir(item.protocolo),
                    title: Text(item.protocolo, style: const TextStyle(fontFamily: 'monospace')),
                    subtitle: item.ocorrencia == null
                        ? Text(item.erro ?? 'Indisponível')
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(rotuloClasse(item.ocorrencia!.classeFinal)),
                              const SizedBox(height: 4),
                              SeloStatus(item.ocorrencia!.status),
                            ],
                          ),
                    trailing: item.ocorrencia == null
                        ? const Icon(Icons.cloud_off_outlined)
                        : Text(formatarData(item.ocorrencia!.criadoEm).split(' ').first),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../estado.dart';
import '../modelos.dart';
import '../rotulos.dart';
import '../servicos/api.dart';
import '../servicos/armazenamento.dart';
import '../widgets/selo_status.dart';

/// Acompanhamento de uma ocorrencia pelo numero de protocolo.
class TelaDetalhe extends StatefulWidget {
  final String protocolo;

  const TelaDetalhe({super.key, required this.protocolo});

  @override
  State<TelaDetalhe> createState() => _TelaDetalheState();
}

class _TelaDetalheState extends State<TelaDetalhe> {
  late Future<OcorrenciaPublica> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = Api.consultar(widget.protocolo);
  }

  Future<void> _recarregar() async {
    // corpo em bloco: o setState nao pode devolver um Future
    setState(() {
      _futuro = Api.consultar(widget.protocolo);
    });
    try {
      await _futuro;
    } catch (_) {
      // o erro ja e exibido pelo FutureBuilder
    }
  }

  Future<void> _salvar() async {
    await Armazenamento.adicionarProtocolo(widget.protocolo);
    Estado.versaoReportes.value++;
    if (!mounted) return;
    setState(() {});
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Adicionado a "Meus reportes"')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final salvo = Armazenamento.protocolos.contains(widget.protocolo);
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.protocolo),
        actions: [
          if (!salvo)
            IconButton(
              tooltip: 'Acompanhar este protocolo',
              onPressed: _salvar,
              icon: const Icon(Icons.bookmark_add_outlined),
            ),
        ],
      ),
      body: FutureBuilder<OcorrenciaPublica>(
        future: _futuro,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('${snapshot.error}', textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    OutlinedButton(onPressed: _recarregar, child: const Text('Tentar de novo')),
                  ],
                ),
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _recarregar,
            child: _conteudo(context, snapshot.data!),
          );
        },
      ),
    );
  }

  Widget _conteudo(BuildContext context, OcorrenciaPublica o) {
    final tema = Theme.of(context);
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: AspectRatio(
            aspectRatio: 4 / 3,
            child: Image.network(
              Api.urlImagem(o.imagemUrl),
              fit: BoxFit.cover,
              errorBuilder: (context, erro, pilha) => Container(
                color: tema.colorScheme.surfaceContainerHighest,
                alignment: Alignment.center,
                child: const Text('Imagem indisponível'),
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(rotuloClasse(o.classeFinal), style: tema.textTheme.titleLarge),
        const SizedBox(height: 6),
        SeloStatus(o.status),
        const SizedBox(height: 8),
        Text(explicacoesStatus[o.status] ?? ''),
        const Divider(height: 32),
        _linha('Você informou', rotuloClasse(o.classeInformada)),
        if (o.classeDetectada != null)
          _linha(
            'Análise automática',
            '${rotuloClasse(o.classeDetectada)} (${formatarPorcentagem(o.confianca)})',
          ),
        _linha('Registrada em', formatarData(o.criadoEm)),
        _linha('Local', '${o.latitude.toStringAsFixed(6)}, ${o.longitude.toStringAsFixed(6)}'),
        if (o.descricao != null) _linha('Descrição', o.descricao!),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () {
              Estado.focoNoMapa.value = LatLng(o.latitude, o.longitude);
              Navigator.of(context).popUntil((rota) => rota.isFirst);
            },
            icon: const Icon(Icons.map_outlined),
            label: const Text('Ver no mapa'),
          ),
        ),
        const Divider(height: 32),
        Text('Andamento', style: tema.textTheme.titleMedium),
        const SizedBox(height: 8),
        for (final evento in o.historico)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.circle, size: 12, color: corDoStatus(evento.status)),
            title: Text(rotuloStatus(evento.status)),
            subtitle: Text(formatarData(evento.em)),
          ),
      ],
    );
  }

  Widget _linha(String rotulo, String valor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(rotulo, style: Theme.of(context).textTheme.bodySmall),
          ),
          Expanded(child: Text(valor)),
        ],
      ),
    );
  }
}

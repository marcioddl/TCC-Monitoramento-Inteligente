import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

import '../estado.dart';
import '../modelos.dart';
import '../rotulos.dart';
import '../servicos/api.dart';
import '../servicos/geocerca.dart';
import '../servicos/localizacao.dart';
import '../widgets/selo_status.dart';
import 'reportar.dart';

/// Mapa com as ocorrencias validadas por perto, o controle dos alertas de
/// proximidade e o botao de reporte.
class TelaInicio extends StatefulWidget {
  const TelaInicio({super.key});

  @override
  State<TelaInicio> createState() => _TelaInicioState();
}

class _TelaInicioState extends State<TelaInicio> {
  static const LatLng _teresina = LatLng(-5.0892, -42.8016);
  static const int _raioBuscaM = 5000;

  final MapController _mapa = MapController();
  final ServicoGeocerca _geo = ServicoGeocerca.instancia;

  bool _mapaPronto = false;
  LatLng? _centroPendente;
  Position? _posicao;
  List<PontoMapa> _pontos = <PontoMapa>[];
  bool _carregando = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    Estado.focoNoMapa.addListener(_aoPedirFoco);
    _localizarECarregar();
  }

  @override
  void dispose() {
    Estado.focoNoMapa.removeListener(_aoPedirFoco);
    super.dispose();
  }

  void _aoPedirFoco() {
    final ponto = Estado.focoNoMapa.value;
    if (ponto != null) _centralizar(ponto, zoom: 17);
  }

  void _centralizar(LatLng ponto, {double zoom = 16}) {
    if (_mapaPronto) {
      _mapa.move(ponto, zoom);
    } else {
      _centroPendente = ponto;
    }
  }

  Future<void> _localizarECarregar() async {
    LatLng centro = _teresina;
    final erro = await Localizacao.garantirPermissao();
    if (erro == null) {
      try {
        final posicao = await Localizacao.posicaoAtual();
        _posicao = posicao;
        centro = LatLng(posicao.latitude, posicao.longitude);
        _centralizar(centro);
      } catch (_) {
        // sem posicao: o mapa fica no centro de Teresina
      }
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
    }
    await _carregarPontos(centro);
  }

  Future<void> _carregarPontos(LatLng centro) async {
    if (!mounted) return;
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final pontos = await Api.mapa(centro.latitude, centro.longitude, raioM: _raioBuscaM);
      if (!mounted) return;
      setState(() => _pontos = pontos);
    } on ErroApi catch (e) {
      if (mounted) setState(() => _erro = e.mensagem);
    } catch (e) {
      if (mounted) setState(() => _erro = 'Falha ao carregar o mapa: $e');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  LatLng _centroAtual() {
    final p = _geo.ultimaPosicao.value ?? _posicao;
    return p == null ? _teresina : LatLng(p.latitude, p.longitude);
  }

  Future<void> _alternarAlertas(bool ligar) async {
    if (ligar) {
      final erro = await _geo.ligar();
      if (erro != null && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(erro)));
      }
    } else {
      await _geo.desligar();
    }
  }

  Future<void> _abrirReporte() async {
    final protocolo = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const TelaReportar()),
    );
    if (protocolo != null) {
      Estado.versaoReportes.value++;
      await _carregarPontos(_centroAtual());
    }
  }

  void _mostrarPonto(PontoMapa ponto) {
    final eu = _geo.ultimaPosicao.value ?? _posicao;
    final distancia = eu == null
        ? null
        : Localizacao.distancia(eu.latitude, eu.longitude, ponto.latitude, ponto.longitude);
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(rotuloClasse(ponto.classe), style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              SeloStatus(ponto.status),
              const SizedBox(height: 12),
              Text(explicacoesStatus[ponto.status] ?? ''),
              const SizedBox(height: 12),
              if (distancia != null) Text('A ${formatarDistancia(distancia)} de você'),
              Text('Registrada em ${formatarData(ponto.criadoEm)}'),
              Text('Alerta de proximidade num raio de ${ponto.raioM} m',
                  style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }

  Widget _cartaoAlertas(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: ValueListenableBuilder<bool>(
          valueListenable: _geo.ativo,
          builder: (context, ativo, _) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SwitchListTile(
                value: ativo,
                onChanged: _alternarAlertas,
                title: const Text('Alertas de proximidade'),
                subtitle: ValueListenableBuilder<String?>(
                  valueListenable: _geo.situacao,
                  builder: (context, situacao, _) => Text(
                    situacao ??
                        (ativo
                            ? 'Ligados: avisaremos a menos de 100 m de um problema.'
                            : 'Desligados.'),
                  ),
                ),
              ),
              if (_erro != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                  child: Text(
                    _erro!,
                    style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(
            child: FlutterMap(
              mapController: _mapa,
              options: MapOptions(
                initialCenter: _teresina,
                initialZoom: 14,
                onMapReady: () {
                  _mapaPronto = true;
                  final pendente = _centroPendente;
                  if (pendente != null) {
                    _centroPendente = null;
                    _mapa.move(pendente, 16);
                  }
                },
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'br.uespi.miiu.miiu_app',
                ),
                CircleLayer(
                  circles: [
                    for (final p in _pontos)
                      CircleMarker(
                        point: LatLng(p.latitude, p.longitude),
                        radius: p.raioM.toDouble(),
                        useRadiusInMeter: true,
                        color: const Color(0x1A2A78D6),
                        borderColor: const Color(0x992A78D6),
                        borderStrokeWidth: 1,
                      ),
                  ],
                ),
                MarkerLayer(
                  markers: [
                    for (final p in _pontos)
                      Marker(
                        point: LatLng(p.latitude, p.longitude),
                        width: 32,
                        height: 32,
                        child: GestureDetector(
                          onTap: () => _mostrarPonto(p),
                          child: MarcadorOcorrencia(classe: p.classe, status: p.status),
                        ),
                      ),
                  ],
                ),
                ValueListenableBuilder<Position?>(
                  valueListenable: _geo.ultimaPosicao,
                  builder: (context, posicao, _) {
                    final p = posicao ?? _posicao;
                    if (p == null) return const SizedBox.shrink();
                    return MarkerLayer(
                      markers: [
                        Marker(
                          point: LatLng(p.latitude, p.longitude),
                          width: 22,
                          height: 22,
                          child: const MarcadorUsuario(),
                        ),
                      ],
                    );
                  },
                ),
                RichAttributionWidget(
                  attributions: [TextSourceAttribution('OpenStreetMap contributors')],
                ),
              ],
            ),
          ),
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(child: _cartaoAlertas(context)),
          ),
          if (_carregando)
            const Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: LinearProgressIndicator(),
            ),
        ],
      ),
      floatingActionButton: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          FloatingActionButton.small(
            heroTag: 'atualizar',
            tooltip: 'Atualizar e centralizar em mim',
            onPressed: () async {
              final centro = _centroAtual();
              _centralizar(centro);
              await _carregarPontos(centro);
            },
            child: const Icon(Icons.my_location),
          ),
          const SizedBox(height: 12),
          FloatingActionButton.extended(
            heroTag: 'reportar',
            onPressed: _abrirReporte,
            icon: const Icon(Icons.add_a_photo_outlined),
            label: const Text('Reportar problema'),
          ),
        ],
      ),
    );
  }
}

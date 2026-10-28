// Estruturas de dados trocadas com a API do MIIU.

double _num(dynamic valor) => (valor as num).toDouble();
double? _numOuNulo(dynamic valor) => valor == null ? null : (valor as num).toDouble();

class OcorrenciaCriada {
  final String protocolo;
  final String status;
  final String classeInformada;
  final String? classeDetectada;
  final double? confianca;
  final DateTime criadoEm;
  final String mensagem;

  OcorrenciaCriada({
    required this.protocolo,
    required this.status,
    required this.classeInformada,
    required this.classeDetectada,
    required this.confianca,
    required this.criadoEm,
    required this.mensagem,
  });

  factory OcorrenciaCriada.fromJson(Map<String, dynamic> j) => OcorrenciaCriada(
        protocolo: j['protocolo'] as String,
        status: j['status'] as String,
        classeInformada: j['classe_informada'] as String,
        classeDetectada: j['classe_detectada'] as String?,
        confianca: _numOuNulo(j['confianca']),
        criadoEm: DateTime.parse(j['criado_em'] as String),
        mensagem: j['mensagem'] as String,
      );
}

class EventoHistorico {
  final String status;
  final DateTime em;

  EventoHistorico(this.status, this.em);

  factory EventoHistorico.fromJson(Map<String, dynamic> j) =>
      EventoHistorico(j['status'] as String, DateTime.parse(j['em'] as String));
}

class OcorrenciaPublica {
  final String protocolo;
  final String status;
  final String classeInformada;
  final String? classeDetectada;
  final String classeFinal;
  final double? confianca;
  final double latitude;
  final double longitude;
  final String? descricao;
  final DateTime criadoEm;
  final DateTime atualizadoEm;
  final List<EventoHistorico> historico;
  final String imagemUrl;

  OcorrenciaPublica({
    required this.protocolo,
    required this.status,
    required this.classeInformada,
    required this.classeDetectada,
    required this.classeFinal,
    required this.confianca,
    required this.latitude,
    required this.longitude,
    required this.descricao,
    required this.criadoEm,
    required this.atualizadoEm,
    required this.historico,
    required this.imagemUrl,
  });

  factory OcorrenciaPublica.fromJson(Map<String, dynamic> j) => OcorrenciaPublica(
        protocolo: j['protocolo'] as String,
        status: j['status'] as String,
        classeInformada: j['classe_informada'] as String,
        classeDetectada: j['classe_detectada'] as String?,
        classeFinal: j['classe_final'] as String,
        confianca: _numOuNulo(j['confianca']),
        latitude: _num(j['latitude']),
        longitude: _num(j['longitude']),
        descricao: j['descricao'] as String?,
        criadoEm: DateTime.parse(j['criado_em'] as String),
        atualizadoEm: DateTime.parse(j['atualizado_em'] as String),
        historico: (j['historico'] as List<dynamic>)
            .map((e) => EventoHistorico.fromJson(e as Map<String, dynamic>))
            .toList(),
        imagemUrl: j['imagem_url'] as String,
      );
}

class PontoMapa {
  final String protocolo;
  final String classe;
  final String status;
  final double latitude;
  final double longitude;
  final int raioM;
  final DateTime criadoEm;

  PontoMapa({
    required this.protocolo,
    required this.classe,
    required this.status,
    required this.latitude,
    required this.longitude,
    required this.raioM,
    required this.criadoEm,
  });

  factory PontoMapa.fromJson(Map<String, dynamic> j) => PontoMapa(
        protocolo: j['protocolo'] as String,
        classe: j['classe'] as String,
        status: j['status'] as String,
        latitude: _num(j['latitude']),
        longitude: _num(j['longitude']),
        raioM: (j['raio_m'] as num).toInt(),
        criadoEm: DateTime.parse(j['criado_em'] as String),
      );
}

class Alerta {
  final String protocolo;
  final String classe;
  final double distanciaM;
  final double latitude;
  final double longitude;
  final int raioM;
  final String mensagem;
  final String canal;

  Alerta({
    required this.protocolo,
    required this.classe,
    required this.distanciaM,
    required this.latitude,
    required this.longitude,
    required this.raioM,
    required this.mensagem,
    required this.canal,
  });

  factory Alerta.fromJson(Map<String, dynamic> j) => Alerta(
        protocolo: j['protocolo'] as String,
        classe: j['classe'] as String,
        distanciaM: _num(j['distancia_m']),
        latitude: _num(j['latitude']),
        longitude: _num(j['longitude']),
        raioM: (j['raio_m'] as num).toInt(),
        mensagem: j['mensagem'] as String,
        canal: j['canal'] as String,
      );
}

class RespostaProximidade {
  final List<Alerta> alertas;
  final bool ignorada;
  final String? motivo;

  RespostaProximidade(this.alertas, this.ignorada, this.motivo);

  factory RespostaProximidade.fromJson(Map<String, dynamic> j) => RespostaProximidade(
        (j['alertas'] as List<dynamic>)
            .map((e) => Alerta.fromJson(e as Map<String, dynamic>))
            .toList(),
        j['ignorada'] as bool? ?? false,
        j['motivo'] as String?,
      );
}

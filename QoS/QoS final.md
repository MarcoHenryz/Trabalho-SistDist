# QoS final

---
"data:": 28-04-2026
"time:": 17:29
source: Implementing an IPv6 QoS management scheme using flow label & class of service fields (Artigo IEEE)
tags:
    - QoS
    - IPv6
    - Redes
aliases:
---

# QoS (Quality of Service) em redes IPV6

## O que é QoS

- Habilidade de um elemento da rede (como uma aplicação ou host) de ter um grau de garantia de que seus requisitos de tráfego e serviço podem ser definidos.
- O QoS em IP baseia-se no conceito de que taxas de transmissão, taxas de erro e outras características dos dados podem ser medidas, melhoradas e, até certo ponto, garantidas antecipadamente.

- Parâmetros para medir o QoS:
    - Atraso (Delay): Tempo decorrido para um pacote passar do remetente através da rede até o receptor (atraso fim-a-fim).
    - Perda de pacotes (Packet Loss): Razão entre o número de pacotes descartados e o total de pacotes enviados.

## Abordagens de QoS

- Para fornecer QoS em uma rede IP, cada um de seus componentes é equipado com novas facilidades e funcionalidades lógicas. São eles:
    - Controle de Admissão (Admission Control): Função que determina se ainda há recursos disponíveis para um serviço solicitado e se eles podem ser fornecidos em uma interface específica.
    - Policiamento e Modelagem (Policing and shaping): É o conjunto de ações realizadas pelo gerenciamento de QoS quando o tráfego real de dados de um fluxo excede os valores que foram solicitados ou negociados em suas especificações de tráfego. Essas ações incluem: descartar pacotes usando agendamentos, rebaixar os pacotes para uma classe de serviço inferior, ou marcar os pacotes como não conformes.
    - Classificador de Pacotes (Packet Classifier): Componente responsável por identificar os pacotes correspondentes a um fluxo particular e associá-los a uma classe de QoS específica designada para aquele fluxo. Essa classificação é implementada nos pontos de borda (edge points) da rede.
    - Agendador de Pacotes (Packet Scheduler): Atua em conjunto com o classificador. É responsável por garantir que os fluxos previamente identificados recebam, de fato, a Qualidade de Serviço solicitada. O agendador também é implementado nos pontos de borda.
- Duas formas são utilizadas para gerenciar QoS nas redes IP:
    - IntServ (Integrated Services): Focado em fornecer garantias de QoS por fluxo individual para sessões de aplicações, utilizando o protocolo RSVP (resource reservation protocol) para sinalizar e configurar o caminho. Sua principal desvantagem é a falta de escalabilidade, pois a carga de armazenamento e processamento nos roteadores aumenta proporcionalmente ao número de fluxos.
    - DiffServ (Differentiated Services): Baseado em um modelo onde o tráfego é condicionado por um bandwidth broker (corretor de largura de banda) e classificado nas bordas da rede através do cabeçalho DSCP (differential code point). Embora mais escalável, apresenta desvantagens como a impossibilidade de diferenciar fluxos individuais dentro da mesma classe e os atrasos gerados pelo mapeamento.

## Protocolo de Próxima Geração (IPv6)

- O IPv6 traz melhorias diretas para o QoS por meio do campo Traffic Class (TC) e do campo identificador Flow Label de 20 bytes.
- O campo TC é usado para diferenciar prioridades, e o Flow Label para distinguir os fluxos vindos da mesma origem de forma exclusiva.
- Essa combinação de IP de origem e rótulo de fluxo gera um tempo menor de busca nas tabelas dos roteadores, minimizando o atraso.

### Flow Label

- Atribuir um valor flow label aos pacotes permite que a rede os classifique utilizando apenas a semântica de IP.
- Isso agiliza o processamento e evita o grave problema da "Violação de Camada" (Layer Violation), que é a prática de tentar extrair dados das camadas de aplicação superiores para processar pacotes.
- Evitar a violação de camada é essencial quando os pacotes trafegam criptografados ou com os números das portas ocultos.

## Controle de Admissão

- O algoritmo que dita se um novo fluxo pode ser atendido pela rede sem prejudicar as reservas já existentes. Avalia a carga atual, recursos solicitados e regras da política do serviço.

### Bandwidth Broker

- É um agente que aloca serviços para usuários e configura os roteadores.
- Ele possui um banco de dados de políticas, verifica se há banda suficiente, aprova a requisição do fluxo e configura o roteador para aceitar o pacote.

### QoSbox

- Trata-se de um roteador configurável que adapta ativamente suas decisões de policiamento e agendamento de acordo com a chegada instantânea do tráfego.
- Ele não depende de agentes externos; ele utiliza buffers por classe e algoritmos locais para gerenciar os atrasos e descartar pacotes caso necessário para manter o serviço das outras classes.

---
"data:": 28-04-2026
"time:": 16:01
source: https://www.techtarget.com/searchcustomerexperience/definition/Quality-of-Experience-QoE-or-QoX
tags:
    - QoE
    - QoS
    - Customer Experience
aliases:
---

# QoE (Definição)

## O que é QoE (Definição)

- A Qualidade de Experiência (QoE ou QoX) é uma medida do nível geral de satisfação e experiência de um cliente com um produto ou serviço e com o fornecedor que o disponibiliza.
- Embora o QoE esteja relacionado à Qualidade de Serviço (QoS), os dois conceitos não são a mesma coisa.
- A União Internacional de Telecomunicações define QoE como a aceitabilidade geral de uma aplicação ou serviço, conforme percebida subjetivamente pelo usuário final.
- O conceito assume a perspectiva do usuário e busca responder à pergunta principal: "Este produto ou serviço entregou uma experiência boa ou suficiente para os usuários finais, e em que medida?".
- O método mais comum e subjetivo para avaliar o QoE é pesquisar ou amostrar um grande número de clientes.

---
"data:": 28-04-2026
"time:": 16:17
source: https://www.geeksforgeeks.org/computer-networks/forward-error-correction-in-computer-networks/
tags:
    - FEC
    - Redes de Computadores
    - Correção de Erros
aliases:
---

# Forward Error Correction (FEC)

- O Forward Error Correction (FEC) é uma técnica que fornece ao receptor a capacidade de corrigir erros e reproduzir pacotes de forma imediata.
- O conceito central é a inserção prévia de redundância matemática nos dados enviados, eliminando a necessidade de estabelecer um canal reverso com a origem para solicitar a retransmissão das informações perdidas ou corrompidas.
- Três técnicas principais de FEC:
    - Distância de Hamming: Método matemático onde a distância mínima necessária para corrigir erros é definida pela expressão d_min = 2t+1. Por exemplo, para corrigir 20 erros, a distância mínima deve ser de 41 bits. Essa técnica raramente é usada em redes por exigir o envio de uma quantidade inviável de bits redundantes.
    - Uso da porta lógica XOR: Técnica que recria pacotes perdidos através da propriedade ou-exclusivo (XOR). Um pacote de dados é dividido em N fragmentos, a operação XOR é calculada entre eles, e a rede envia N+1 fragmentos. Na prática, se N=4, envia-se 25% de dados adicionais, permitindo a correção caso um dos quatro fragmentos seja perdido.
    - Entrelaçamento de Fragmentos (Chunk Interleaving): Cada pacote de dados é dividido em pequenos blocos criados horizontalmente, mas que são combinados e enviados em pacotes verticalmente. Assim, cada pacote transmitido carrega um pequeno pedaço de vários pacotes originais diferentes.

## Exemplo de uso

- O FEC é amplamente utilizado em comunicações multimídia de tempo real.
- Ao utilizar a técnica de *Chunk Interleaving* (Entrelaçamento), se um pacote for completamente perdido durante a transmissão, o receptor perderá apenas um fragmento muito pequeno de cada pacote original.
- Como pequenos fragmentos ausentes são normalmente aceitáveis em fluxos de áudio ou vídeo, a reprodução continua sem interrupções perceptíveis.

## Relação com QoS

- A retransmissão de pacotes perdidos ou corrompidos é inviável para aplicações em tempo real, pois cria um atraso inaceitável na reprodução (é necessário esperar até que o dado seja reenviado pela rede).
- A principal relação do FEC com o QoS está na capacidade de garantir o parâmetro de Atraso (*Delay*) e Variação de Atraso (*Jitter*). Ao reproduzir pacotes perdidos no próprio destino instantaneamente, o FEC protege a fluidez da aplicação e mantém os requisitos restritos de tráfego, evitando a degradação da Qualidade de Serviço.
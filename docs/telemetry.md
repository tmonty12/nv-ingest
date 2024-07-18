# Telemetry

## Docker compose

To run OpenTelemetry locally, run

```shell
$ docker compose up otel-collector
```

Once and OpenTelemetry and Zipkin are running, you can open your browser to explore traces: [http://localhost:9411/zipkin/](http://localhost:9411/zipkin/).

![](images/zipkin.png)

To run Prometheus, run

```shell
$ docker compose up prometheus
```

Once Promethus is running, you can open your browser to explore metrics: [http://localhost:9090/](http://localhost:9090/)

![](images/prometheus.png)

## Helm chart

TODO
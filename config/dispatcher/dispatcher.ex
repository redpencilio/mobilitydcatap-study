defmodule Dispatcher do
  use Matcher

  define_accept_types [
    html: ["text/html", "application/xhtml+html"],
    json: ["application/json", "application/vnd.api+json"],
    any: ["*/*"]
  ]

  define_layers [:api, :frontend, :not_found]

  # JSON API: jobs resource (mu-cl-resources)
  match "/api/jobs/*path", %{accept: %{json: true}, layer: :api} do
    forward conn, path, "http://resource/jobs/"
  end

  # Static report files
  get "/reports/*path", %{layer: :api} do
    forward conn, path, "http://reports/reports/"
  end

  # Frontend catch-all (EmberJS handles client-side routing)
  match "/*path", %{accept: %{html: true}, layer: :frontend} do
    forward conn, path, "http://frontend/"
  end

  match "/*path", %{accept: %{any: true}, layer: :frontend} do
    forward conn, path, "http://frontend/"
  end

  match "/*_path", %{layer: :not_found} do
    send_resp(conn, 404, "{\"error\": \"not found\"}")
  end
end

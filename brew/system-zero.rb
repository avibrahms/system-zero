class SystemZero < Formula
  desc "One-click autonomy and self-improvement for any repository"
  homepage "https://systemzero.dev"
  url "https://files.pythonhosted.org/packages/source/s/sz-cli/sz_cli-0.1.0.tar.gz"
  sha256 "e829d683b422c3b0113e98baa91fb81483a2c13eb3ca67b5a4f543ab77e1122b"
  license "Apache-2.0"
  depends_on "pipx"

  def install
    (bin/"sz").write <<~EOS
      #!/usr/bin/env bash
      exec "#{Formula["pipx"].opt_bin}/pipx" run --spec git+https://github.com/avibrahms/system-zero@v0.1.0 sz "$@"
    EOS
  end

  test do
    assert_match "0.1.0", shell_output("#{bin}/sz --version")
  end
end

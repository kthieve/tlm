# Placeholder for 0.3.0 — publish to a tap when ready.
class Tlm < Formula
  desc "Terminal LLM helper"
  homepage "https://github.com/OWNER/tlm"
  url "https://github.com/OWNER/tlm/archive/refs/tags/v0.2.0b1.tar.gz"
  sha256 "REPLACE"
  license "MIT"
  depends_on "python@3.11"

  def install
    virtualenv_install_with_resources
  end
end

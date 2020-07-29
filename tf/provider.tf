terraform {
  required_providers {
    aws = "~> 2.62"
  }
  backend "s3" {
    bucket = "tfstate-apachecontainer"
    key    = "dev/terraform.tfstate"
    region = "us-east-1"
  }
}

variable "allowed_account_id" {
  default = "141517001380" # custa-sbox1
}

provider "aws" {
  region              = "us-east-1"
  profile             = "custa-sbox1"
  allowed_account_ids = ["${var.allowed_account_id}"]
}

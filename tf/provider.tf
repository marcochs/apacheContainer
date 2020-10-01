variable "allowed_account_id" {
  type    = string
  default = "141517001380"
}

variable "aws_profile" {
  type    = string
  default = "custa-sbox1"
}


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

provider "aws" {
  region              = "us-east-1"
  profile             = var.aws_profile
  allowed_account_ids = ["${var.allowed_account_id}"]
}

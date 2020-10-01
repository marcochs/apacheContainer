
output "listener_rule_arn_dev" {
  value = aws_lb_listener_rule.host_based_routing.id
}

output "service_blue" {
  value = aws_ecs_service.acblue.id
}

output "service_green" {
  value = aws_ecs_service.acgreen.id
}

output "tg_green" {
  value = aws_lb_target_group.green.id
}

output "tg_blue" {
  value = aws_lb_target_group.blue.id
}

output "fqdn_green" {
  value = var.fqdn_green
}

output "fqdn_blue" {
  value = var.fqdn_blue
}

variable "vpc-id" {
  type    = string
  default = "vpc-0329496e4c54c5617"
}

variable "sg-elb-id" {
  type    = string
  default = "sg-03cd8e59d4108bdf6"
}

variable "sg-ecs-id" {
  type    = string
  default = "sg-05a15e864d696a25a"
}

variable "subnet-elb-us-east-1a-id" {
  type    = string
  default = "subnet-0f9f97be8ed75575a"
}

variable "subnet-elb-us-east-1b-id" {
  type    = string
  default = "subnet-074327b623eead742"
}

variable "subnet-elb-us-east-1c-id" {
  type    = string
  default = "subnet-0695e08573e70c5e7"
}

variable "subnet-private-us-east-1a-id" {
  type    = string
  default = "subnet-0b3ac8c90ce9c3126"
}

variable "subnet-private-us-east-1b-id" {
  type    = string
  default = "subnet-074fc05e463ca7de2"
}

variable "subnet-private-us-east-1c-id" {
  type    = string
  default = "subnet-033a6e87720fdf16d"
}

variable "elb-logs-bucket" {
  type    = string
  default = "logs-apachecontainer"
}

variable "fqdn_blue" {
  type    = string
  default = "acdev-blue.cloudmindful.com"
}

variable "fqdn_green" {
  type    = string
  default = "acdev-green.cloudmindful.com"
}

variable "r53_zone_id" {
  type    = string
  default = "Z0798797FJ9OHRG3WUX2"
}

variable "r53_alb_cname" {
  type    = string
  default = "acdev.vpc1.custa-sbox1.cloudmindful.com"
}

variable "r53_alb_cname_blue" {
  type    = string
  default = "acdev-blue.vpc1.custa-sbox1.cloudmindful.com"
}

variable "r53_alb_cname_green" {
  type    = string
  default = "acdev-green.vpc1.custa-sbox1.cloudmindful.com"
}

resource "aws_lb" "dev" {
  name               = "apachecontainer-dev"
  internal           = false
  load_balancer_type = "application"
  security_groups    = ["${var.sg-elb-id}"]
  subnets            = ["${var.subnet-elb-us-east-1a-id}", "${var.subnet-elb-us-east-1b-id}", "${var.subnet-elb-us-east-1c-id}"]

  enable_deletion_protection = false

  access_logs {
    bucket  = var.elb-logs-bucket
    prefix  = "dev-lb"
    enabled = true
  }

  tags = {
    env = "dev"
  }
}

resource "aws_route53_record" "devlb" {
  zone_id = var.r53_zone_id
  name    = var.r53_alb_cname
  type    = "CNAME"
  ttl     = "300"
  records = ["${aws_lb.dev.dns_name}"]
}

resource "aws_route53_record" "devlb-blue" {
  zone_id = var.r53_zone_id
  name    = var.r53_alb_cname_blue
  type    = "CNAME"
  ttl     = "300"
  records = ["${aws_lb.dev.dns_name}"]
}

resource "aws_route53_record" "devlb-green" {
  zone_id = var.r53_zone_id
  name    = var.r53_alb_cname_green
  type    = "CNAME"
  ttl     = "300"
  records = ["${aws_lb.dev.dns_name}"]
}

resource "aws_lb_target_group" "blue" {
  name        = "apachecontainer-blue-tg${substr(uuid(), 0, 3)}"
  port        = 80
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc-id

  # this finally makes me smile defautl was 300... five long minutes...
  # we don't need a delay because the service is not in rotation.
  # try with 0 first and see if that can be stable...
  deregistration_delay = 0

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [name]
  }
}

resource "aws_lb_target_group" "blog" {
  name        = "apachecontainer-blog"
  port        = 80
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc-id

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [name]
  }
}

# move from docker on jump to fargate no longer needed
resource "aws_lb_target_group_attachment" "blog" {
  target_group_arn = aws_lb_target_group.blog.arn
  target_id        = "10.94.32.230"
  port             = 80
}


resource "aws_lb_listener" "dev443" {
  load_balancer_arn = aws_lb.dev.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  #  certificate_arn   = "arn:aws:acm:us-east-1:141517001380:certificate/e31e3b4a-fdfa-4be1-a9f8-bd32470b0077"
  certificate_arn = "arn:aws:acm:us-east-1:141517001380:certificate/95c6d210-cee6-4370-bc08-c41e0e670736"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.blue.arn
  }
}

resource "aws_lb_listener_rule" "host_based_routing" {
  listener_arn = aws_lb_listener.dev443.arn
  priority     = 99

  action {
    type = "forward"
    forward {
      target_group {
        arn    = aws_lb_target_group.blue.arn
        weight = 100
      }

      target_group {
        arn    = aws_lb_target_group.green.arn
        weight = 0
      }

      stickiness {
        enabled  = true
        duration = 60
      }

    }
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}

resource "aws_lb_listener_rule" "host_based_routing_blue" {
  listener_arn = aws_lb_listener.dev443.arn
  priority     = 89

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.blue.arn
  }

  condition {
    host_header {
      values = [aws_route53_record.devlb-blue.name, var.fqdn_blue]
    }
  }
}

resource "aws_lb_listener_rule" "host_based_routing_blog" {
  listener_arn = aws_lb_listener.dev443.arn
  priority     = 87

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.blog.arn
  }

  condition {
    host_header {
      values = ["cloudmindful.com"]
    }
  }
}

resource "aws_lb_listener_rule" "host_based_routing_green" {
  listener_arn = aws_lb_listener.dev443.arn
  priority     = 88

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.green.arn
  }

  condition {
    host_header {
      values = [aws_route53_record.devlb-green.name, var.fqdn_green]
    }
  }
}


resource "aws_lb_listener" "dev80" {
  load_balancer_arn = aws_lb.dev.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_ecs_cluster" "actest" {
  name = "actest"
}


resource "aws_ecs_task_definition" "apacheContainer" {
  family                   = "apache"
  container_definitions    = file("task-definitions/apache.json")
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = "arn:aws:iam::141517001380:role/ecsTaskExecutionRole"
}


resource "aws_ecs_service" "acgreen" {
  name                               = "acgreen"
  cluster                            = aws_ecs_cluster.actest.id
  task_definition                    = aws_ecs_task_definition.apacheContainer.arn
  desired_count                      = 1
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 50
  launch_type                        = "FARGATE"
  force_new_deployment               = true
  depends_on                         = [aws_lb_target_group.green]

  load_balancer {
    target_group_arn = aws_lb_target_group.green.arn
    container_name   = "apache2"
    container_port   = 80
  }

  network_configuration {
    subnets          = ["${var.subnet-private-us-east-1a-id}", "${var.subnet-private-us-east-1b-id}", "${var.subnet-private-us-east-1c-id}"]
    security_groups  = [var.sg-ecs-id]
    assign_public_ip = false
  }

  # maybe use these later... for now I want it spun up, not ignored that it's down
  lifecycle {
    ignore_changes = [desired_count, task_definition, capacity_provider_strategy, launch_type]
  }

  deployment_controller {
    type = "ECS"
  }
}

resource "aws_ecs_service" "acblue" {
  name                               = "acblue"
  cluster                            = aws_ecs_cluster.actest.id
  task_definition                    = aws_ecs_task_definition.apacheContainer.arn
  desired_count                      = 1
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 50
  launch_type                        = "FARGATE"
  force_new_deployment               = true
  depends_on                         = [aws_lb_target_group.blue]

  load_balancer {
    target_group_arn = aws_lb_target_group.blue.arn
    container_name   = "apache2"
    container_port   = 80
  }

  network_configuration {
    subnets          = ["${var.subnet-private-us-east-1a-id}", "${var.subnet-private-us-east-1b-id}", "${var.subnet-private-us-east-1c-id}"]
    security_groups  = [var.sg-ecs-id]
    assign_public_ip = false
  }

  # maybe use these later... for now I want it spun up, not ignored that it's down
  lifecycle {
    ignore_changes = [desired_count, task_definition, capacity_provider_strategy, launch_type]
  }

  deployment_controller {
    type = "ECS"
  }
}

resource "aws_lb_target_group" "green" {
  name                 = "apachecontainer-green-tg${substr(uuid(), 0, 3)}"
  port                 = 80
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc-id
  deregistration_delay = 0

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [name]
  }
}

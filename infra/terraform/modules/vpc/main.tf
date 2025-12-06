resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-vpc"
    }
  )
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-igw"
    }
  )
}

# Public subnets
resource "aws_subnet" "public" {
  for_each = {
    for idx, cidr in var.public_subnet_cidrs :
    idx => cidr
  }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value
  map_public_ip_on_launch = true

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-public-${each.key}"
      "Tier" = "public"
    }
  )
}

# Private subnets
resource "aws_subnet" "private" {
  for_each = {
    for idx, cidr in var.private_subnet_cidrs :
    idx => cidr
  }

  vpc_id     = aws_vpc.this.id
  cidr_block = each.value

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-private-${each.key}"
      "Tier" = "private"
    }
  )
}

# Public route table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-public-rt"
    }
  )
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# NAT gateway (optional, single AZ)
resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? 1 : 0

  vpc = true

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-nat-eip"
    }
  )
}

resource "aws_nat_gateway" "this" {
  count = var.enable_nat_gateway ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = element(values(aws_subnet.public)[*].id, 0)

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-nat-gw"
    }
  )
}

# Private route table (only if NAT is enabled)
resource "aws_route_table" "private" {
  count = var.enable_nat_gateway ? 1 : 0

  vpc_id = aws_vpc.this.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[0].id
  }

  tags = merge(
    var.tags,
    {
      "Name" = "${var.tags["Project"] != "" ? var.tags["Project"] : "app"}-private-rt"
    }
  )
}

resource "aws_route_table_association" "private" {
  for_each = var.enable_nat_gateway ? aws_subnet.private : {}

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[0].id
}

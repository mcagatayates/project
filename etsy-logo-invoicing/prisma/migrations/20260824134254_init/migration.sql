-- CreateEnum
CREATE TYPE "OrderStatus" AS ENUM ('DETECTED', 'PARSED', 'VALIDATED', 'DRAFT_CREATED', 'FINALIZED', 'MANUAL_REVIEW', 'FAILED_RETRYABLE', 'FAILED_PERMANENT', 'CANCELLED');

-- CreateEnum
CREATE TYPE "OrderSource" AS ENUM ('EMAIL_ONLY', 'EMAIL_AND_API');

-- CreateTable
CREATE TABLE "orders" (
    "id" TEXT NOT NULL,
    "shopId" TEXT NOT NULL,
    "etsyOrderId" TEXT NOT NULL,
    "source" "OrderSource" NOT NULL DEFAULT 'EMAIL_ONLY',
    "mailMessageId" TEXT,
    "mailHash" TEXT NOT NULL,
    "rawPayloadEncrypted" TEXT NOT NULL,
    "normalizedOrderJson" JSONB,
    "validationResult" JSONB,
    "status" "OrderStatus" NOT NULL DEFAULT 'DETECTED',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoices" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "logoInvoiceId" TEXT,
    "externalReference" TEXT NOT NULL,
    "invoiceNumber" TEXT,
    "invoiceStatus" TEXT NOT NULL,
    "requestHash" TEXT NOT NULL,
    "requestPayloadRedacted" JSONB NOT NULL,
    "responsePayloadRedacted" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "invoices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "processing_attempts" (
    "id" TEXT NOT NULL,
    "orderId" TEXT NOT NULL,
    "operation" TEXT NOT NULL,
    "attemptNumber" INTEGER NOT NULL,
    "status" TEXT NOT NULL,
    "errorCode" TEXT,
    "errorMessageRedacted" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "processing_attempts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audit_logs" (
    "id" TEXT NOT NULL,
    "entityType" TEXT NOT NULL,
    "entityId" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "metadataRedacted" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "orders_mailHash_idx" ON "orders"("mailHash");

-- CreateIndex
CREATE INDEX "orders_status_idx" ON "orders"("status");

-- CreateIndex
CREATE UNIQUE INDEX "orders_shopId_etsyOrderId_key" ON "orders"("shopId", "etsyOrderId");

-- CreateIndex
CREATE UNIQUE INDEX "invoices_orderId_key" ON "invoices"("orderId");

-- CreateIndex
CREATE UNIQUE INDEX "invoices_externalReference_key" ON "invoices"("externalReference");

-- CreateIndex
CREATE INDEX "invoices_logoInvoiceId_idx" ON "invoices"("logoInvoiceId");

-- CreateIndex
CREATE INDEX "processing_attempts_orderId_idx" ON "processing_attempts"("orderId");

-- CreateIndex
CREATE INDEX "audit_logs_entityType_entityId_idx" ON "audit_logs"("entityType", "entityId");

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "orders"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "processing_attempts" ADD CONSTRAINT "processing_attempts_orderId_fkey" FOREIGN KEY ("orderId") REFERENCES "orders"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

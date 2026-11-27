import { DownloadSimpleIcon, XIcon } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { type Attachment, downloadAttachment } from '@/features/claims/api'
import { errorMessage } from '@/lib/api'

/** Fetches a receipt (bearer-token protected) and shows it inline: image or PDF. */
export function ReceiptViewer({
  claimId,
  attachment,
  onClose,
}: {
  claimId: number
  attachment: Attachment
  onClose: () => void
}) {
  const blobQuery = useQuery({
    queryKey: ['claims', 'detail', claimId, 'attachment', attachment.id],
    queryFn: () => downloadAttachment(claimId, attachment.id),
    staleTime: Infinity,
  })
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!blobQuery.data) return
    const objectUrl = URL.createObjectURL(blobQuery.data)
    // Object URLs are an external resource: create + revoke them in step with the blob.
    // oxlint-disable-next-line react/set-state-in-effect
    setUrl(objectUrl)
    return () => {
      URL.revokeObjectURL(objectUrl)
      setUrl(null)
    }
  }, [blobQuery.data])

  const type = blobQuery.data?.type || attachment.content_type
  const isImage = type.startsWith('image/')
  const isPdf = type === 'application/pdf'

  return (
    <Card className="lg:sticky lg:top-4" aria-label="Receipt viewer">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="truncate text-sm" title={attachment.original_name}>
          {attachment.original_name}
        </CardTitle>
        <div className="flex items-center gap-1">
          {url && (
            <a
              href={url}
              download={attachment.original_name}
              className={buttonVariants({ variant: 'ghost', size: 'icon-sm' })}
              aria-label="Download receipt"
            >
              <DownloadSimpleIcon />
            </a>
          )}
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close receipt">
            <XIcon />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {blobQuery.isPending && <Skeleton className="h-[480px] w-full" />}
        {blobQuery.isError && (
          <Alert variant="destructive">
            <AlertDescription>
              Couldn't load the receipt. {errorMessage(blobQuery.error)}
            </AlertDescription>
          </Alert>
        )}
        {url && isImage && (
          <img
            src={url}
            alt={`Receipt ${attachment.original_name}`}
            className="max-h-[70vh] w-full rounded-md border object-contain"
          />
        )}
        {url && isPdf && (
          <object
            data={url}
            type="application/pdf"
            className="h-[70vh] w-full rounded-md border"
            aria-label={`Receipt ${attachment.original_name}`}
          >
            <p className="text-sm text-muted-foreground">
              PDF preview unavailable. Use the download button.
            </p>
          </object>
        )}
        {url && !isImage && !isPdf && (
          <p className="text-sm text-muted-foreground">
            No preview for this file type. Use the download button.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
